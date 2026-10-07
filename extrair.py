"""
Extrator de Dados de Propostas e Contratos com IA

Lê documentos (PDF ou TXT) de uma pasta, usa um modelo de linguagem para extrair
os dados principais (cliente, objeto, valor, prazos, obrigações, riscos) e gera:
  - um JSON por documento em saida/
  - uma planilha consolidada saida/resumo.csv

Uso:
    python extrair.py                      # lê a pasta documentos/
    python extrair.py --pasta contratos/
    python extrair.py --mock               # testa sem chave de API
"""

import argparse
import csv
import json
import os
import re
import sys
import time
from pathlib import Path

LIMITE_CARACTERES = 60_000  # evita mandar documentos gigantes de uma vez

INSTRUCOES = """Você extrai dados de propostas comerciais e contratos em português.
Responda APENAS com um JSON válido, sem texto antes ou depois, sem crases:
{
  "tipo_documento": "proposta" | "contrato" | "aditivo" | "outro",
  "cliente": "<nome do contratante>",
  "fornecedor": "<nome do contratado>",
  "objeto": "<o que está sendo contratado, em uma frase>",
  "valor_total": "<valor com moeda, ou null>",
  "forma_pagamento": "<resumo, ou null>",
  "prazo_execucao": "<prazo, ou null>",
  "data_assinatura": "<AAAA-MM-DD, ou null>",
  "obrigacoes_fornecedor": ["<item>", "..."],
  "pontos_de_atencao": ["<multas, riscos, cláusulas incomuns>", "..."]
}
Use null quando a informação não estiver no documento. Nunca invente valores."""

COLUNAS_CSV = ["arquivo", "tipo_documento", "cliente", "fornecedor", "objeto",
               "valor_total", "forma_pagamento", "prazo_execucao",
               "data_assinatura", "pontos_de_atencao"]


def ler_documento(caminho: Path) -> str:
    """Extrai o texto de um PDF ou TXT."""
    if caminho.suffix.lower() == ".pdf":
        from pypdf import PdfReader
        paginas = PdfReader(str(caminho)).pages
        texto = "\n".join(p.extract_text() or "" for p in paginas)
        if not texto.strip():
            raise ValueError("PDF sem texto (provavelmente escaneado; precisaria de OCR)")
        return texto
    return caminho.read_text(encoding="utf-8")


def extrair_json(texto: str) -> dict:
    texto = texto.strip().replace("```json", "").replace("```", "")
    inicio, fim = texto.find("{"), texto.rfind("}")
    if inicio == -1 or fim == -1:
        raise ValueError("Resposta sem JSON")
    return json.loads(texto[inicio:fim + 1])


def resposta_mock(texto: str) -> dict:
    """Extração simples por regex, só para testar o fluxo sem API."""
    valor = re.search(r"R\$\s?[\d\.]+,\d{2}", texto)
    prazo = re.search(r"(\d+)\s*\(?[a-z ]*\)?\s*dias", texto, re.IGNORECASE)
    return {
        "tipo_documento": "contrato" if "contrato" in texto.lower() else "proposta",
        "cliente": "[mock]",
        "fornecedor": "[mock]",
        "objeto": "[mock] " + texto.strip().splitlines()[0][:80],
        "valor_total": valor.group(0) if valor else None,
        "forma_pagamento": None,
        "prazo_execucao": prazo.group(0) if prazo else None,
        "data_assinatura": None,
        "obrigacoes_fornecedor": [],
        "pontos_de_atencao": ["[mock] multa" ] if "multa" in texto.lower() else [],
    }


def extrair_com_ia(cliente, modelo: str, texto: str, tentativas: int = 3) -> dict:
    ultimo_erro = None
    for tentativa in range(1, tentativas + 1):
        try:
            resposta = cliente.messages.create(
                model=modelo,
                max_tokens=1500,
                system=INSTRUCOES,
                messages=[{"role": "user", "content": f"Documento:\n\n{texto[:LIMITE_CARACTERES]}"}],
            )
            saida = "".join(b.text for b in resposta.content if b.type == "text")
            return extrair_json(saida)
        except Exception as erro:
            ultimo_erro = erro
            espera = 2 ** tentativa
            print(f"   tentativa {tentativa} falhou ({erro}); aguardando {espera}s")
            time.sleep(espera)
    raise RuntimeError(f"Falhou após {tentativas} tentativas: {ultimo_erro}")


def main():
    parser = argparse.ArgumentParser(description="Extrai dados de propostas e contratos com IA")
    parser.add_argument("--pasta", default="documentos")
    parser.add_argument("--saida", default="saida")
    parser.add_argument("--mock", action="store_true", help="roda sem API")
    args = parser.parse_args()

    arquivos = sorted(p for p in Path(args.pasta).iterdir() if p.suffix.lower() in {".pdf", ".txt"})
    if not arquivos:
        sys.exit(f"Nenhum PDF ou TXT encontrado em {args.pasta}/")

    cliente, modelo = None, os.getenv("MODELO", "claude-haiku-5-5")
    if not args.mock:
        if not os.getenv("ANTHROPIC_API_KEY"):
            sys.exit("Defina ANTHROPIC_API_KEY ou rode com --mock.")
        import anthropic
        cliente = anthropic.Anthropic()

    pasta_saida = Path(args.saida)
    pasta_saida.mkdir(exist_ok=True)
    linhas = []

    for i, arquivo in enumerate(arquivos, 1):
        print(f"[{i}/{len(arquivos)}] {arquivo.name}")
        try:
            texto = ler_documento(arquivo)
            dados = resposta_mock(texto) if args.mock else extrair_com_ia(cliente, modelo, texto)
        except Exception as erro:
            print(f"   ERRO: {erro}")
            dados = {"erro": str(erro)}

        (pasta_saida / f"{arquivo.stem}.json").write_text(
            json.dumps(dados, ensure_ascii=False, indent=2), encoding="utf-8")

        linha = {"arquivo": arquivo.name}
        for coluna in COLUNAS_CSV[1:]:
            valor = dados.get(coluna)
            linha[coluna] = " | ".join(valor) if isinstance(valor, list) else (valor or "")
        if "erro" in dados:
            linha["pontos_de_atencao"] = f"ERRO: {dados['erro']}"
        linhas.append(linha)

    with open(pasta_saida / "resumo.csv", "w", encoding="utf-8-sig", newline="") as f:
        escritor = csv.DictWriter(f, fieldnames=COLUNAS_CSV, delimiter=";")
        escritor.writeheader()
        escritor.writerows(linhas)

    print(f"\nPronto: {len(linhas)} documento(s) em {pasta_saida}/ (resumo.csv + JSONs)")


if __name__ == "__main__":
    main()

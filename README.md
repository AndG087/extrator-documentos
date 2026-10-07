# Extrator de Dados de Propostas e Contratos com IA

## O problema
Empresas acumulam propostas e contratos em PDF, e as informações importantes (valor, prazo, multas, obrigações) ficam escondidas no texto. Para saber "quanto temos a receber" ou "qual contrato tem multa pesada", alguém precisa abrir arquivo por arquivo.

## O que o projeto faz
Lê todos os PDFs e TXTs de uma pasta, extrai o texto, pede para um modelo de linguagem identificar os dados principais e gera:

- `saida/<arquivo>.json`, com os dados completos de cada documento;
- `saida/resumo.csv`, uma planilha consolidada com tipo, cliente, fornecedor, objeto, valor, pagamento, prazo, data e pontos de atenção.

## Como rodar
```bash
pip install -r requirements.txt

# Teste sem API (extração simples por regex):
python extrair.py --mock

# Com IA de verdade:
export ANTHROPIC_API_KEY="sua-chave"
python extrair.py
```
Opções: `--pasta contratos/`, `--saida resultados/`, variável `MODELO`.

## O que aprendi com o modo mock
A versão por regex encontra valores em R$ com facilidade, mas erra o prazo do contrato de exemplo: pega "60 dias" do aviso de renovação em vez dos 12 meses de vigência. Regras fixas não entendem contexto, e é aí que o modelo de linguagem faz diferença.

## Decisões técnicas
- **`null` em vez de invenção:** o prompt proíbe inventar valores e pede `null` quando o dado não existe.
- **Limite de tamanho:** documentos muito longos são cortados para controlar custo.
- **PDF escaneado é detectado:** se o PDF não tem texto, o erro avisa que seria preciso OCR.
- **Retentativas e erro isolado por arquivo**, como no qualificador de leads.

## Próximos passos
- OCR para PDFs escaneados.
- Dividir documentos longos em partes e juntar os resultados.
- Alertas automáticos para prazos de renovação próximos.

# Localização de Hubs: Single e Multiple Allocation

Aplicação interativa em **Python e Streamlit** para estudar redes logísticas do tipo
**hub-and-spoke**. O projeto resolve modelos de localização de hubs com o Gurobi e
permite comparar uma formulação baseada em custos médios com uma formulação que
utiliza custos produzidos por Aproximação Contínua (CA).

O estudo utiliza uma instância com regiões do estado de São Paulo, matriz de fluxos,
coordenadas geográficas e custos de coleta, transferência inter-hub e entrega.

## Objetivo

Em uma rede hub-and-spoke, os fluxos saem de uma origem, passam por um ou dois hubs
e seguem até o destino:

```text
origem → primeiro hub → segundo hub → destino
```

O modelo escolhe exatamente `p` hubs e define a rota de cada par origem–destino com
o objetivo de minimizar o custo total de transporte.

O projeto busca responder questões como:

- quais pontos devem funcionar como hubs;
- quais rotas são utilizadas por cada fluxo;
- quanto fluxo passa por um ou dois hubs;
- onde estão os arcos mais carregados da rede;
- quanto é gasto em coleta, inter-hub e entrega;
- como os resultados mudam entre o modelo normal e o modelo com CA.

## Modelos disponíveis

### Multiple Allocation com CA

Utiliza as matrizes de custo de coleta e entrega fornecidas pela instância. O custo
inter-hub é calculado por:

```text
C_hub(k,m) = alpha × c_hub × distância(k,m)
```

Na instância atual:

- capacidade do caminhão inter-hub: `Q_hub = 32.000` pacotes;
- custo do caminhão: `ckm_hub = R$ 6,01/km`;
- custo unitário: `c_hub = 6,01 / 32.000 = R$ 0,0001878125/pacote·km`;
- fator inter-hub padrão: `alpha = 0,75`.

### Multiple Allocation normal

Calcula os custos a partir das distâncias geográficas e de coeficientes unitários
fixos de coleta, transferência e entrega. Essa versão serve como referência para a
comparação com os custos provenientes da Aproximação Contínua.

### Single Allocation

O repositório também contém a implementação de Single Allocation, na qual cada nó
é associado a um único hub. O painel atual está concentrado na comparação entre as
duas versões de Multiple Allocation.

## Função objetivo

Para cada fluxo `w(i,j)` e rota `i → k → m → j`, o custo considerado é:

```text
w(i,j) × [C_col(i,k) + C_hub(k,m) + C_ent(m,j)]
```

Quando `k = m`, a rota utiliza apenas um hub e não possui trecho inter-hub.

## Recursos do painel

O aplicativo permite:

- selecionar a instância, o número de nós e a quantidade de hubs;
- alternar entre Multiple normal e Multiple com CA;
- ajustar `alpha`, `c_hub` e o tempo limite do solver;
- visualizar hubs e rotas no mapa;
- consultar a tabela completa de rotas;
- analisar fluxos agregados por arco;
- comparar rotas que utilizam um ou dois hubs;
- comparar fluxo de coleta, inter-hub e entrega;
- analisar custos totais e custos por pacote;
- comparar financeiramente os dois modelos;
- inspecionar parâmetros e matrizes da instância;
- consultar status, gap, tempo e log do Gurobi.

Para obter o comparativo lado a lado, execute uma vez o modelo **Multiple com CA** e
uma vez o **Multiple normal**, mantendo a mesma instância, número de nós e quantidade
de hubs. Os resultados ficam armazenados durante a sessão do Streamlit.

## Estrutura do projeto

```text
.
├── app_streamlit.py              # Interface e análises comparativas
├── multiple_allocation.py        # Formulação Multiple Allocation com custos CA
├── multiple_allocation_normal.py # Formulação Multiple baseada em distância
├── single_allocation.py          # Formulação Single Allocation
├── utilidades.py                 # Leitura, mapas, gráficos e logs
├── requirements.txt              # Dependências Python
├── data/SPdata/                   # Instâncias e dados geográficos
├── sp_spatial_gravity_model/      # Geração da instância e matrizes de custo
└── documentação/                  # Referências acadêmicas do projeto
```

## Requisitos

- Python 3.10 ou superior;
- Gurobi Optimizer;
- licença válida do Gurobi;
- pacotes listados em `requirements.txt`.

O pacote `gurobipy` instala a interface Python, mas não substitui a ativação de uma
licença do Gurobi. Licenças acadêmicas podem ser obtidas conforme as condições da
Gurobi Optimization.

## Instalação

Clone o repositório e entre na pasta:

```bash
git clone https://github.com/lauranascimentoo/Projeto-Single-e-Multiple-Allocation-com-Strealite.git
cd Projeto-Single-e-Multiple-Allocation-com-Strealite
```

Crie e ative um ambiente virtual.

No Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

No Linux ou macOS:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

Instale as dependências:

```bash
pip install -r requirements.txt
```

## Execução

Com o ambiente virtual ativo e a licença do Gurobi configurada:

```bash
streamlit run app_streamlit.py
```

O Streamlit exibirá no terminal o endereço local da aplicação, normalmente
`http://localhost:8501`.

## Formato da instância

Os arquivos em `data/SPdata` contêm, nesta ordem:

1. número de nós;
2. latitude e longitude de cada nó;
3. matriz de fluxos origem–destino;
4. matriz de custos de coleta;
5. matriz de custos de entrega;
6. parâmetros nomeados da instância.

Entre os parâmetros estão demanda total, capacidade dos veículos, custos por
quilômetro e dados usados na construção das matrizes por Aproximação Contínua.

## Interpretação das análises

O fluxo origem–destino é o mesmo nos dois modelos. O que muda é o caminho escolhido
para transportá-lo. Por isso, valores totais de fluxo podem ser parecidos mesmo
quando as rotas e os custos são diferentes.

Na análise financeira, o **custo por pacote** é especialmente importante para
comparar grupos com volumes diferentes. O custo total das rotas com dois hubs pode
ser maior simplesmente porque essas rotas transportam uma parcela maior da demanda.

## Observações

- os resultados dependem dos parâmetros e da instância selecionada;
- arquivos em `outputs/` e `logs/` são gerados durante a execução e ignorados pelo Git;
- a licença acadêmica do Gurobi deve ser usada somente de acordo com seus termos;
- o projeto tem finalidade acadêmica e experimental.

## Referências

- Campbell, J. F. (1996). *Hub location and the p-hub median problem*.
- Stokkink & Geroliminis (2025), material disponível na pasta `documentação/`.

## Autoria

Projeto desenvolvido por:

- [Laura Nascimento](https://github.com/lauranascimentoo)
- [Rafael Campello](https://github.com/Rafioio)

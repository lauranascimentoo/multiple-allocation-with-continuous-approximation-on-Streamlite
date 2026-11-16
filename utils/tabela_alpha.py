
import csv
import sys

import multiple_allocation_normal
from configs.paths import OUTPUTS_DIR
from utils import run_model as run_model_module
from utils.indicadores_de_comparacao import executar_comparacao

ALPHAS = [0, 0.1, 0.3, 0.5, 0.75, 1]
INSTANCE = {"relative_path": "data/SPdata/sp11_instancia_ordenada.txt"}
N_LIMIT = 11
P = 5
TIME_LIMIT = 300


def _status(solucao):
    from gurobipy import GRB

    return {
        GRB.OPTIMAL: "Ótimo",
        GRB.TIME_LIMIT: "Limite de tempo",
    }.get(solucao["model_status"], f"Status {solucao['model_status']}")


def executar(alpha):
    resultados = {}

    for modelo in ("multiple_normal", "multiple_ca"):
        resultados[modelo] = run_model_module.run_model(
            model_name=modelo,
            instance=INSTANCE,
            n_limit=N_LIMIT,
            override_p=P,
            alpha=alpha,
            time_limit=TIME_LIMIT,
        )

        if not resultados[modelo]["ok"]:
            raise RuntimeError(
                f"alpha={alpha}, modelo={modelo}: "
                f"{resultados[modelo].get('error') or 'sem solução válida'}"
            )

    return resultados["multiple_normal"], resultados["multiple_ca"]


def gerar():
    linhas = []

    for alpha in ALPHAS:
        print(f"\nExecutando alpha = {alpha}...")

        sol_t, sol_ac = executar(alpha)

        ind = executar_comparacao(sol_t, sol_ac, alpha=alpha)

        # Indicador 1: Hubs coincidentes
        i1 = ind["indicador_1"]["hubs_comuns"]

        # Indicador 2: Índice de Jaccard
        i2 = ind["indicador_2"]["jaccard"]

        # Indicador 3: Demanda realocada
        i3 = ind["indicador_3"]

        # Indicador 4: Distâncias médias de acesso
        i4_t = ind["indicador_4"]["tradicional"]
        i4_ac = ind["indicador_4"]["aproximacao_continua"]

        # Indicador 5: Perfil de custos
        i5_t = ind["indicador_5"]["tradicional"]
        i5_ac = ind["indicador_5"]["aproximacao_continua"]

        # Indicador 6: Benefício percentual
        i6 = ind["indicador_6"]["beneficio_percentual"]

        # Indicador 7: Tempo e gap
        i7_t = ind["indicador_7"]["tradicional"]
        i7_ac = ind["indicador_7"]["aproximacao_continua"]

        linha = {
            "alpha": alpha,

            # Indicador 1
            "I1 - Hubs comuns": i1,

            # Indicador 2
            "I2 - Jaccard": i2,

            # Indicador 3
            "I3 - Demanda realocada (%)": i3["percentual_realocada"],
            "I3 - Pares alterados": i3["pares_alterados"],

            # Indicador 4
            "I4 - Distância coleta T": i4_t["distancia_coleta"],
            "I4 - Distância entrega T": i4_t["distancia_entrega"],
            "I4 - Distância total T": i4_t["distancia_total"],

            "I4 - Distância coleta AC": i4_ac["distancia_coleta"],
            "I4 - Distância entrega AC": i4_ac["distancia_entrega"],
            "I4 - Distância total AC": i4_ac["distancia_total"],

            # Indicador 5
            "I5 - Custo coleta T": i5_t["custo_coleta"],
            "I5 - Custo entrega T": i5_t["custo_entrega"],
            "I5 - Custo inter-hub T": i5_t["custo_inter_hub"],
            "I5 - Custo total T": i5_t["custo_total"],
            "I5 - Custo por pacote T": i5_t["custo_por_pacote"],

            "I5 - Custo coleta AC": i5_ac["custo_coleta"],
            "I5 - Custo entrega AC": i5_ac["custo_entrega"],
            "I5 - Custo inter-hub AC": i5_ac["custo_inter_hub"],
            "I5 - Custo total AC": i5_ac["custo_total"],
            "I5 - Custo por pacote AC": i5_ac["custo_por_pacote"],

            # Indicador 6
            "I6 - Benefício AC (%)": i6,

            # Indicador 7
            "I7 - Tempo T (s)": i7_t["tempo"],
            "I7 - Gap T (%)": 100 * i7_t["gap"],
            "I7 - Tempo AC (s)": i7_ac["tempo"],
            "I7 - Gap AC (%)": 100 * i7_ac["gap"],

            # Informações complementares dos modelos
            "Objetivo T": sol_t["objective"],
            "Objetivo AC": sol_ac["objective"],
            "Status T": _status(sol_t),
            "Status AC": _status(sol_ac),
        }

        linhas.append(linha)

        print(
            f"Alpha {alpha}: "
            f"I1={i1}, "
            f"I2={i2:.4f}, "
            f"I3={i3['percentual_realocada']:.4f}%, "
            f"I6={i6:.4f}%"
        )

    return linhas


def main():
    OUTPUTS_DIR.mkdir(exist_ok=True)

    linhas = gerar()

    caminho = OUTPUTS_DIR / "tabela_alpha_indicadores.csv"

    with open(caminho, "w", newline="", encoding="utf-8-sig") as arquivo:
        writer = csv.DictWriter(
            arquivo,
            fieldnames=list(linhas[0].keys()),
            delimiter=";",
        )

        writer.writeheader()

        for linha in linhas:
            linha_formatada = {
                k: (
                    round(v, 4)
                    if isinstance(v, float)
                    else v
                )
                for k, v in linha.items()
            }

            writer.writerow({
                k: (
                    f"{v:.4f}".replace(".", ",")
                    if isinstance(v, float)
                    else v
                )
                for k, v in linha_formatada.items()
            })


    print(f"\n{'=' * 60}")
    print("TABELA DE INDICADORES GERADA")
    print(f"Arquivo: {caminho}")
    print(f"Quantidade de alphas: {len(linhas)}")
    print(f"Quantidade de indicadores: 7")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    sys.exit(main())

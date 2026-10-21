"""Gera a tabela de resultados por alpha em duas versões:

- "sem_alpha2": c_hub (já com alpha) entra uma única vez no objetivo.
- "com_alpha2": alpha multiplica c_hub de novo nos dois modelos (alpha ao quadrado),
  como era antes do commit 60f226c. A avaliação C_AC usa a mesma matriz do M_AC.

Uso (a partir da raiz do projeto):
    python -m utils.tabela_alpha
"""

import csv
import sys
from math import isclose

import multiple_allocation_normal
from gurobipy import GRB
from configs.paths import OUTPUTS_DIR
from utils import run_model as run_model_module
from utils.indicadores_de_comparacao import executar_comparacao

ALPHAS = [0, 0.1, 0.3, 0.5, 0.75, 1]
INSTANCE = {"relative_path": "data/SPdata/sp11_instancia_ordenada.txt"}
N_LIMIT = 11
P = 5
TIME_LIMIT = 300

_solver_original = run_model_module.solve_multiple_allocation_p_hub


def _solver_alpha2(**kwargs):
    kwargs["c_hub"] = {k: kwargs["alpha"] * v for k, v in kwargs["c_hub"].items()}
    return _solver_original(**kwargs)


def _executar(alpha, alpha2):
    solver = _solver_alpha2 if alpha2 else _solver_original
    run_model_module.solve_multiple_allocation_p_hub = solver
    multiple_allocation_normal.solve_multiple_allocation_p_hub = solver

    resultados = {}
    for modelo in ("multiple_normal", "multiple_ca"):
        resultados[modelo] = run_model_module.run_model(
            model_name=modelo, instance=INSTANCE, n_limit=N_LIMIT,
            override_p=P, alpha=alpha, time_limit=TIME_LIMIT,
        )
        if not resultados[modelo]["ok"]:
            raise RuntimeError(f"alpha={alpha} {modelo}: {resultados[modelo].get('error') or 'sem solução ótima'}")

    if alpha2:
        for r in resultados.values():
            r["c_hub_matrix"] = {k: alpha * v for k, v in r["c_hub_matrix"].items()}
    return resultados["multiple_normal"], resultados["multiple_ca"]


def _status(solucao):
    return {GRB.OPTIMAL: "Ótimo", GRB.TIME_LIMIT: "Limite de tempo"}.get(
        solucao["model_status"], f"Status {solucao['model_status']}"
    )


def gerar(alpha2):
    linhas = []
    for alpha in ALPHAS:
        sol_t, sol_ac = _executar(alpha, alpha2)
        ind = executar_comparacao(sol_t, sol_ac)["indicador_5"]
        c_st = ind["tradicional"]["custo_total"]
        c_sac = ind["aproximacao_continua"]["custo_total"]
        confere = isclose(c_sac, sol_ac["objective"], rel_tol=1e-9, abs_tol=1e-4)
        linhas.append({
            "alpha": alpha,
            "C_AC(S_T)": c_st,
            "C_AC(S_AC)": c_sac,
            "B_AC (%)": 100.0 * (c_st - c_sac) / c_st,
            "Função objetivo T": sol_t["objective"],
            "Função objetivo AC": sol_ac["objective"],
            "tempo T (s)": sol_t["runtime"],
            "tempo AC (s)": sol_ac["runtime"],
            "status T": _status(sol_t),
            "status AC": _status(sol_ac),
            "gap T (%)": 100 * sol_t["gap"],
            "gap AC (%)": 100 * sol_ac["gap"],
            "C_AC(S_AC)==obj AC": confere,
        })
    return linhas


def main():
    OUTPUTS_DIR.mkdir(exist_ok=True)
    for nome, alpha2 in (("sem_alpha2", False), ("com_alpha2", True)):
        linhas = gerar(alpha2)
        caminho = OUTPUTS_DIR / f"tabela_alpha_{nome}.csv"
        with open(caminho, "w", newline="", encoding="utf-8-sig") as f:
            w = csv.DictWriter(f, fieldnames=list(linhas[0]), delimiter=";")
            w.writeheader()
            w.writerows(linhas)
        print(f"\n== {nome} -> {caminho}")
        for l in linhas:
            print({k: (round(v, 4) if isinstance(v, float) else v) for k, v in l.items()})


if __name__ == "__main__":
    sys.exit(main())

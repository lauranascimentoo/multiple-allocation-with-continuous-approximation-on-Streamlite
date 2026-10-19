"""Teste manual: Multiple Allocation tradicional (solve_multiple_allocation_normal).

Le instancias nos formatos:
  1) "AP/CAB por tamanho": 10.3.4, 15.3.4, 20.3.4, 25.3.4
       n, coordenadas, matriz de fluxos W, p, chi, alpha, delta
  2) CAB25.txt: n, matriz de fluxos W, matriz de distancias D (sem coordenadas)
  3) okelly.txt: tabela "param: W C :=" com linhas "i j Wij Cij"
     (formatos 2 e 3 nao trazem p/alpha: use --p e --alpha, padrao p=3 e alpha=0.4)

Uso (a partir da raiz do projeto):
    python test.py
    python test.py data/CABdata/25.3.4
    python test.py data/CABdata/CAB25.txt --p 3 --alpha 0.4
    python test.py data/CABdata/okelly.txt --n 20 --p 3 --alpha 0.4
"""

import argparse
import math
import re

INSTANCE_PATH = "data/CABdata/15.3.4"
TIME_LIMIT = 300

# Otimos de referencia (enumeracao exata, alocacao multipla, p=3, alpha=0.4,
# chi=delta=1, distancias euclidianas das coordenadas das instancias CAB).
REFERENCE_P3_A04 = {
    10: (825848546.9493, [3, 4, 7]),
    15: (3173387583.8253, [4, 7, 12]),
    20: (6975317647.5240, [4, 12, 17]),
    25: (10902054801.9662, [12, 17, 21]),
}


def _read_matrix(tokens, pos, n):
    m = []
    for _ in range(n):
        m.append([float(t) for t in tokens[pos:pos + n]])
        pos += n
    return m, pos


def _read_okelly(text, n_sub):
    """Formato okelly.txt: linhas 'i j Wij Cij' apos 'param: W C :='."""
    body = text[text.index(":=") + 2:]
    rows = []
    for line in body.splitlines():
        parts = line.split()
        if len(parts) == 4 and re.fullmatch(r"\d+", parts[0]) and re.fullmatch(r"\d+", parts[1]):
            rows.append((int(parts[0]), int(parts[1]), float(parts[2]), float(parts[3])))
    n_full = max(r[0] for r in rows)
    n = n_sub or n_full
    flows = [[0.0] * n for _ in range(n)]
    dist = [[0.0] * n for _ in range(n)]
    for i, j, w, c in rows:
        if i <= n and j <= n:  # subconjuntos 10/15/20 = submatriz do canto superior esquerdo
            flows[i - 1][j - 1] = w
            dist[i - 1][j - 1] = c
    return n, flows, dist


def read_instance(path, p=None, alpha=None, n_sub=None):
    """Retorna n, flows, dist, p, chi, alpha, delta (dist = matriz n x n)."""
    with open(path, encoding="latin-1") as f:
        text = f.read()

    # Formato 3: okelly.txt
    if ":=" in text and "param" in text:
        n, flows, dist = _read_okelly(text, n_sub)
        return n, flows, dist, (p or 3), 1.0, (alpha if alpha is not None else 0.4), 1.0

    tokens = text.split()
    n = int(float(tokens[0]))

    # Formato 1: n + coords + W + (p, chi, alpha, delta)
    if len(tokens) == 1 + 2 * n + n * n + 4:
        pos = 1
        coords = []
        for _ in range(n):
            coords.append((float(tokens[pos]), float(tokens[pos + 1])))
            pos += 2
        flows, pos = _read_matrix(tokens, pos, n)
        f_p = int(float(tokens[pos]))
        chi = float(tokens[pos + 1])
        f_alpha = float(tokens[pos + 2])
        delta = float(tokens[pos + 3])
        dist = [[math.dist(a, b) for b in coords] for a in coords]
        return n, flows, dist, (p or f_p), chi, (alpha if alpha is not None else f_alpha), delta

    # Formato 2: CAB25.txt -> n + W + D
    if len(tokens) == 1 + 2 * n * n:
        flows, pos = _read_matrix(tokens, 1, n)
        dist, pos = _read_matrix(tokens, pos, n)
        return n, flows, dist, (p or 3), 1.0, (alpha if alpha is not None else 0.4), 1.0

    raise ValueError(
        f"Formato nao reconhecido em {path}: n={n}, {len(tokens)} tokens "
        f"(esperado {1 + 2*n + n*n + 4} ou {1 + 2*n*n})."
    )


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("instance", nargs="?", default=INSTANCE_PATH)
    ap.add_argument("--p", type=int, default=None, help="numero de hubs (sobrescreve o arquivo)")
    ap.add_argument("--alpha", type=float, default=None, help="fator de desconto (sobrescreve o arquivo)")
    ap.add_argument("--n", type=int, default=None, help="so para okelly.txt: usa os n primeiros nos")
    ap.add_argument("--time-limit", type=float, default=TIME_LIMIT)
    args = ap.parse_args()

    # Importados aqui para o leitor poder ser testado sem Gurobi instalado.
    from gurobipy import GRB
    from multiple_allocation_normal import solve_multiple_allocation_normal

    status_names = {
        GRB.OPTIMAL: "OPTIMAL", GRB.INFEASIBLE: "INFEASIBLE", GRB.INF_OR_UNBD: "INF_OR_UNBD",
        GRB.UNBOUNDED: "UNBOUNDED", GRB.TIME_LIMIT: "TIME_LIMIT",
        GRB.INTERRUPTED: "INTERRUPTED", GRB.SUBOPTIMAL: "SUBOPTIMAL",
    }

    instance_path = args.instance
    n, flows, dist, p, chi, alpha, delta = read_instance(
        instance_path, p=args.p, alpha=args.alpha, n_sub=args.n
    )

    nodes = list(range(1, n + 1))
    flow = {(i, j): flows[i - 1][j - 1] for i in nodes for j in nodes}
    distance = {(i, j): dist[i - 1][j - 1] for i in nodes for j in nodes}

    print("=" * 70)
    print("MODELO: Multiple Allocation tradicional (solve_multiple_allocation_normal)")
    print("=" * 70)
    print(f"Instancia: {instance_path} | n={n} | p={p}")
    print(f"Coeficientes: coleta={chi}, transferencia(alpha)={alpha}, distribuicao={delta}")
    if chi != 1.0 or delta != 1.0:
        print("ATENCAO: solve_multiple_allocation_normal usa coleta=1 e distribuicao=1 fixos;")
        print(f"         so alpha={alpha} e aplicado (entre hubs).")

    result = solve_multiple_allocation_normal(
        nodes=nodes, flow=flow, distance=distance, p=p, alpha=alpha,
        instance_path=instance_path, time_limit=args.time_limit,
    )

    mdl = result[0]
    hubs = result[1] if len(result) > 1 else []
    routes = result[2] if len(result) > 2 else {}

    print("\n" + "-" * 70)
    print("RESULTADO")
    print("-" * 70)

    if mdl is None:
        print("Status: modelo nao foi criado (erro de inicializacao ou timeout antes da otimizacao).")
        print("=" * 70)
        return

    print(f"Status Gurobi: {mdl.Status} ({status_names.get(mdl.Status, 'OUTRO')})")
    print(f"Tempo de execucao (Gurobi): {mdl.Runtime:.3f} s")

    if mdl.SolCount == 0 or not routes:
        print("Sem solucao disponivel (inviavel, limite de tempo ou erro).")
        print("=" * 70)
        return

    print(f"Funcao objetivo: {mdl.ObjVal:.6f}")
    if mdl.IsMIP:
        print(f"Melhor limite: {mdl.ObjBound:.6f} | Gap: {mdl.MIPGap:.4%}")
    print(f"Hubs selecionados: {hubs}")

    print("\nRotas escolhidas:")
    for (i, j), (k, m) in routes.items():
        print(f"{i} -> {j}: {i} -> hub {k} -> hub {m} -> {j}")
    print("=" * 70)


if __name__ == "__main__":
    main()
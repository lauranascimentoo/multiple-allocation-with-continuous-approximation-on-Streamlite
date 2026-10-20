EPS = 1e-9

# ---------------------------------------------------------------------------
# Validação
# ---------------------------------------------------------------------------

def _validar_solucao(solucao, nome):
    for campo in ("selected_hubs", "x_values", "alpha"):
        if campo not in solucao or solucao[campo] is None:
            raise ValueError(
                f"Campo obrigatório '{campo}' ausente no dicionário da solução '{nome}'. "
                f"Ele deve vir do resultado do solver (dicionário de saída do modelo)."
            )


def _validar_obrigatorios(**kwargs):
    for nome, valor in kwargs.items():
        if valor is None:
            raise ValueError(
                f"Parâmetro obrigatório '{nome}' não foi informado. "
                f"Ele deve ser obtido da instância do problema, não pode ser inventado."
            )

# ---------------------------------------------------------------------------
# Indicador 1 e 2 — hubs coincidentes e Jaccard (eq. 2 e 3)
# ---------------------------------------------------------------------------

def indicador1_hubs_comuns(hubs_t, hubs_ac):
    return len(set(hubs_t) & set(hubs_ac))


def indicador2_jaccard(hubs_t, hubs_ac):
    ht, hac = set(hubs_t), set(hubs_ac)
    uniao = ht | hac
    if not uniao:
        return 0.0
    return len(ht & hac) / len(uniao)


# ---------------------------------------------------------------------------
# Indicador 3 — percentual de demanda realocada (eq. 4)
# ---------------------------------------------------------------------------

def indicador3_demanda_realocada(x_t, x_ac, flow):
    """P_realoc = 100 * (1/2) * sum_ijkm w_ij|xT-xAC| / sum_ij w_ij
    Pares (i,j) alterados: distribuição de x_ijkm diferente entre as soluções."""
    chaves = set(x_t) | set(x_ac)
    dif_por_par = {}
    for (i, j, k, m) in chaves:
        xt = x_t.get((i, j, k, m), 0.0)
        xac = x_ac.get((i, j, k, m), 0.0)
        dif_por_par[(i, j)] = dif_por_par.get((i, j), 0.0) + abs(xt - xac)

    soma_w = sum(flow.values())
    if soma_w == 0:
        raise ValueError("Soma de flow[(i,j)] é zero; não é possível calcular o percentual de demanda realocada.")

    soma_ponderada = sum(flow.get((i, j), 0.0) * dif for (i, j), dif in dif_por_par.items())
    percentual = 100.0 * 0.5 * soma_ponderada / soma_w
    pares_alterados = sum(1 for v in dif_por_par.values() if v > EPS)
    return percentual, pares_alterados


# ---------------------------------------------------------------------------
# Indicador 4 — distância média ponderada de acesso (eq. 5-8)
# ---------------------------------------------------------------------------

def indicador4_distancia_acesso(x_values, flow, distance):
    soma_w = sum(flow.values())
    if soma_w == 0:
        raise ValueError("Soma de flow[(i,j)] é zero; não é possível calcular a distância média.")

    soma_col = 0.0
    soma_ent = 0.0
    for (i, j, k, m), xijkm in x_values.items():
        wij = flow.get((i, j))
        if wij is None:
            raise ValueError(f"flow[{(i, j)}] ausente; necessário para o indicador 4.")
        d_ik = distance.get((i, k))
        d_mj = distance.get((m, j))
        if d_ik is None or d_mj is None:
            raise ValueError(f"distance ausente para ({i},{k}) ou ({m},{j}); necessário para o indicador 4.")
        soma_col += d_ik * wij * xijkm
        soma_ent += d_mj * wij * xijkm

    d_col = soma_col / soma_w
    d_ent = soma_ent / soma_w
    return {"distancia_coleta": d_col, "distancia_entrega": d_ent, "distancia_total": d_col + d_ent}


# ---------------------------------------------------------------------------
# Indicador 5 — perfil de custos sob regra comum de avaliação (eq. 9-16)
# ---------------------------------------------------------------------------

def indicador5_perfil_custos(x_values, flow, c_col, c_ent, c_hub_matrix):
    """Avalia uma solução com as mesmas matrizes de custo do modelo M_AC.
    c_col e c_ent já incluem o percurso interno e c_hub_matrix já inclui alpha,
    então NÃO multiplicar por c ou alpha de novo."""
    custo_coleta = 0.0
    custo_entrega = 0.0
    custo_inter_hub = 0.0

    for (i, j, k, m), xijkm in x_values.items():
        fluxo_rota = flow[(i, j)] * xijkm

        custo_coleta += fluxo_rota * c_col[(i, k)]
        custo_entrega += fluxo_rota * c_ent[(m, j)]
        custo_inter_hub += fluxo_rota * c_hub_matrix[(k, m)]

    custo_total = custo_coleta + custo_entrega + custo_inter_hub

    soma_w = sum(flow.values())
    if soma_w == 0:
        raise ValueError("Soma dos fluxos é zero; custo por pacote indefinido.")

    return {
        "custo_coleta": custo_coleta,
        "custo_entrega": custo_entrega,
        "custo_inter_hub": custo_inter_hub,
        "custo_total": custo_total,
        "custo_por_pacote": custo_total / soma_w,
    }

# ---------------------------------------------------------------------------
# Indicador 6 — benefício da solução AC (eq. 18)
# ---------------------------------------------------------------------------

def indicador6_beneficio(cac_t, cac_ac):
    if cac_t == 0:
        raise ValueError("CAC(ST) é zero; benefício percentual (indicador 6) indefinido.")
    return 100.0 * (cac_t - cac_ac) / cac_t


# ---------------------------------------------------------------------------
# Função principal
# ---------------------------------------------------------------------------


def comparar_solucoes(solucao_t, solucao_ac, flow, distance,
                       c_col, c_ent, c_hub_matrix):
    _validar_solucao(solucao_t, "tradicional")
    _validar_solucao(solucao_ac, "aproximacao_continua")
    _validar_obrigatorios(
        flow=flow,
        distance=distance,
        c_col=c_col,
        c_ent=c_ent,
        c_hub_matrix=c_hub_matrix,
    )

    hubs_t, hubs_ac = solucao_t["selected_hubs"], solucao_ac["selected_hubs"]
    x_t, x_ac = solucao_t["x_values"], solucao_ac["x_values"]

    percentual_realocada, pares_alterados = indicador3_demanda_realocada(x_t, x_ac, flow)

    perfil_t = indicador5_perfil_custos(
        x_t, flow, c_col, c_ent, c_hub_matrix
    )

    perfil_ac = indicador5_perfil_custos(
        x_ac, flow, c_col, c_ent, c_hub_matrix
    )

    return {
        "indicador_1": {"hubs_comuns": indicador1_hubs_comuns(hubs_t, hubs_ac)},
        "indicador_2": {"jaccard": indicador2_jaccard(hubs_t, hubs_ac)},
        "indicador_3": {"percentual_realocada": percentual_realocada, "pares_alterados": pares_alterados},
        "indicador_4": {
            "tradicional": indicador4_distancia_acesso(x_t, flow, distance),
            "aproximacao_continua": indicador4_distancia_acesso(x_ac, flow, distance),
        },
        "indicador_5": {"tradicional": perfil_t, "aproximacao_continua": perfil_ac},
        "indicador_6": {
            "beneficio_percentual": indicador6_beneficio(perfil_t["custo_total"], perfil_ac["custo_total"])
        },
    }


def executar_comparacao(solucao_t, solucao_ac, alpha=None):
    _validar_solucao(solucao_t, "tradicional")
    _validar_solucao(solucao_ac, "aproximacao_continua")

    if not solucao_t.get("ok"):
        raise ValueError("O modelo Multiple normal não encontrou uma solução válida.")
    if not solucao_ac.get("ok"):
        raise ValueError("O modelo Multiple com CA não encontrou uma solução válida.")
    if solucao_t["params"] != solucao_ac["params"]:
        raise ValueError(
            "Os parâmetros das duas soluções não coincidem. "
            "Não é possível comparar soluções de instâncias diferentes."
        )
    
    alpha_t, alpha_ac = solucao_t["alpha"], solucao_ac["alpha"]
    
    if abs(alpha_t - alpha_ac) > EPS:
        raise ValueError(
            f"As soluções foram resolvidas com alphas diferentes "
            f"(normal={alpha_t}, CA={alpha_ac}). Execute os dois modelos novamente "
            f"com o mesmo alpha."
        )
    if alpha is not None and abs(alpha - alpha_t) > EPS:
        raise ValueError(
            f"O alpha informado ({alpha}) difere do alpha das soluções ({alpha_t})."
        )

    for campo in ("flow", "c_col", "c_ent", "c_hub_matrix"):
        if solucao_t[campo] != solucao_ac[campo]:
            raise ValueError(
                f"As soluções possuem dados diferentes em '{campo}'."
            )

    return comparar_solucoes(
        solucao_t=solucao_t,
        solucao_ac=solucao_ac,
        flow=solucao_ac["flow"],
        distance=solucao_ac["distance"],
        c_col=solucao_ac["c_col"],
        c_ent=solucao_ac["c_ent"],
        c_hub_matrix=solucao_ac["c_hub_matrix"],
    )

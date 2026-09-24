EPS = 1e-9

# ---------------------------------------------------------------------------
# Validação
# ---------------------------------------------------------------------------

def _validar_solucao(solucao, nome):
    for campo in ("selected_hubs", "x_values"):
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

def _oi_dj(flow):
    """Oi = sum_j w_ij ; Dj = sum_i w_ij (eq. 10)"""
    Oi, Dj = {}, {}
    for (i, j), w in flow.items():
        Oi[i] = Oi.get(i, 0.0) + w
        Dj[j] = Dj.get(j, 0.0) + w
    return Oi, Dj

def _custo_inter_hub(x_values, flow, distance, alpha, c_hub):
    """Eq. 15, com Chub_km = c_hub * d_km (eq. 16)."""
    total = 0.0
    for (i, j, k, m), xijkm in x_values.items():
        wij = flow.get((i, j))
        if wij is None:
            raise ValueError(f"flow[{(i, j)}] ausente; necessário para o custo inter-hub.")
        d_km = distance.get((k, m))
        if d_km is None:
            raise ValueError(f"distance[{(k, m)}] ausente; necessário para o custo inter-hub.")
        total += wij * xijkm * alpha * (c_hub * d_km)
    return total

def _custo_acesso(x_values, flow, d_acesso_col, d_acesso_ent, c, Oi, Dj):
    """Eq. 12. d_acesso_col[(i,k)] e d_acesso_ent[(m,j)] já vêm com
    2*d*R embutido (calculado no pipeline de geração da instância),
    então NÃO multiplicar por 2 de novo aqui."""
    total = 0.0
    for (i, j, k, m), xijkm in x_values.items():
        oi, dj = Oi.get(i, 0.0), Dj.get(j, 0.0)
        if oi == 0 or dj == 0:
            continue
        wij = flow.get((i, j))
        if wij is None:
            raise ValueError(f"flow[{(i, j)}] ausente; necessário para o custo de acesso.")
        d_ik = d_acesso_col.get((i, k))
        d_mj = d_acesso_ent.get((m, j))
        if d_ik is None or d_mj is None:
            raise ValueError(f"d_acesso ausente para ({i},{k}) ou ({m},{j}); necessário para o custo de acesso.")
        total += wij * xijkm * c * (d_ik / oi + d_mj / dj)
    return total


def _custo_interno(x_values, flow, d_interno_col, d_interno_ent, c, Oi, Dj):
    """Eq. 14. d_interno_col[i] / d_interno_ent[j] já vêm com β√(A·N) embutido."""
    total = 0.0
    for (i, j, k, m), xijkm in x_values.items():
        oi, dj = Oi.get(i, 0.0), Dj.get(j, 0.0)
        if oi == 0 or dj == 0:
            continue
        d_i = d_interno_col.get(i)
        d_j = d_interno_ent.get(j)
        if d_i is None or d_j is None:
            raise ValueError(f"d_interno ausente para a região {i} ou {j}; necessário para o custo interno.")
        wij = flow.get((i, j))
        if wij is None:
            raise ValueError(f"flow[{(i, j)}] ausente; necessário para o custo interno.")
        total += wij * xijkm * c * (d_i / oi + d_j / dj)
    return total


def indicador5_perfil_custos(x_values, flow, distance, alpha, c_hub, c,
                              d_acesso_col, d_acesso_ent, d_interno_col, d_interno_ent):
    Oi, Dj = _oi_dj(flow)
    custo_acesso = _custo_acesso(x_values, flow, d_acesso_col, d_acesso_ent, c, Oi, Dj)
    custo_interno = _custo_interno(x_values, flow, d_interno_col, d_interno_ent, c, Oi, Dj)
    custo_inter_hub = _custo_inter_hub(x_values, flow, distance, alpha, c_hub)
    custo_total = custo_acesso + custo_interno + custo_inter_hub

    soma_w = sum(flow.values())
    if soma_w == 0:
        raise ValueError("Soma de flow[(i,j)] é zero; não é possível calcular o custo por pacote.")

    return {
        "custo_acesso": custo_acesso,
        "custo_interno": custo_interno,
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
                       d_acesso_col, d_acesso_ent, d_interno_col, d_interno_ent,
                       alpha, c_hub, c):
    _validar_solucao(solucao_t, "tradicional")
    _validar_solucao(solucao_ac, "aproximacao_continua")
    _validar_obrigatorios(
        flow=flow, distance=distance,
        d_acesso_col=d_acesso_col, d_acesso_ent=d_acesso_ent,
        d_interno_col=d_interno_col, d_interno_ent=d_interno_ent,
        alpha=alpha, c_hub=c_hub, c=c,
    )

    hubs_t, hubs_ac = solucao_t["selected_hubs"], solucao_ac["selected_hubs"]
    x_t, x_ac = solucao_t["x_values"], solucao_ac["x_values"]

    percentual_realocada, pares_alterados = indicador3_demanda_realocada(x_t, x_ac, flow)

    perfil_t = indicador5_perfil_custos(x_t, flow, distance, alpha, c_hub, c,
                                         d_acesso_col, d_acesso_ent, d_interno_col, d_interno_ent)
    perfil_ac = indicador5_perfil_custos(x_ac, flow, distance, alpha, c_hub, c,
                                          d_acesso_col, d_acesso_ent, d_interno_col, d_interno_ent)

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


def executar_comparacao(solucao_t, solucao_ac, alpha):
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

    params = solucao_t["params"]

    return comparar_solucoes(
        solucao_t=solucao_t,
        solucao_ac=solucao_ac,
        flow=solucao_t["flow"],           # <- vem da raiz do dict, não de params
        distance=solucao_t["distance"],   # <- idem
        d_acesso_col=solucao_t["d_acesso_col"],
        d_acesso_ent=solucao_t["d_acesso_ent"],
        d_interno_col=solucao_t["d_interno_col"],
        d_interno_ent=solucao_t["d_interno_ent"],
        alpha=alpha,
        c_hub=params["c_hub"],   
        c=params["c_col"],          
    )

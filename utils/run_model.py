from gurobipy import GRB
import os
import io
import time
import contextlib
from pathlib import Path
from multiple_allocation import solve_multiple_allocation_p_hub
from utilidades import load_sp_instance, plot_solution
from configs.paths import ROOT_DIR, OUTPUTS_DIR
from multiple_allocation_normal import solve_multiple_allocation_normal

SOLVERS = {
    "multiple_ca": solve_multiple_allocation_p_hub,
    "multiple_normal": solve_multiple_allocation_normal,
}

def run_model(
    model_name,
    instance,
    n_limit,
    override_p,
    alpha,
    time_limit,
):
    os.environ["MPLBACKEND"] = "Agg"
    os.environ["SP_SKIP_PLOT_SHOW"] = "1"
    os.makedirs(OUTPUTS_DIR, exist_ok=True)

    previous_cwd = Path.cwd()
    buffer = io.StringIO()
    started = time.perf_counter()

    try:
        os.chdir(ROOT_DIR)
        data = load_sp_instance(
            file_path=instance["relative_path"],
            n_limit=n_limit,
            override_p=override_p,
            alpha=alpha,
        )
        nodes, coords, flow, distance, p = (
            data["nodes"], data["coords"], data["flow"], data["distance"], data["p"]
        )

        with contextlib.redirect_stdout(buffer), contextlib.redirect_stderr(buffer):
            common_args = {
                "nodes": nodes,
                "flow": flow,
                "distance": distance,
                "p": p,
                "instance_path": instance["relative_path"],
                "time_limit": time_limit,
                "alpha": alpha,
            }
            if model_name == "multiple_ca":
                route_c_col, route_c_ent, route_c_hub = data["c_col"], data["c_ent"], data["c_hub"]
                model, selected_hubs, selected_routes, x_values = solve_multiple_allocation_p_hub(
                    nodes=nodes,
                    flow=flow,
                    distance=distance,
                    p=p,
                    alpha=alpha,
                    c_col=data["c_col"],
                    c_ent=data["c_ent"],
                    c_hub=data["c_hub"],
                    instance_path=instance["relative_path"],
                    time_limit=time_limit,
                )
                
            else:
                route_c_col = data["c_col"]
                route_c_hub = data["c_hub"]
                route_c_ent = data["c_ent"]
                model, selected_hubs, selected_routes, x_values = solve_multiple_allocation_normal(
                    nodes=nodes,
                    flow=flow,
                    distance=distance,
                    p=p,
                    alpha=alpha,
                    instance_path=instance["relative_path"],
                    time_limit=time_limit,
                )

            image_path = None
            if selected_hubs:
                image_path = OUTPUTS_DIR / f"sp_solution_{model_name}.png"
                plot_solution(
                    coords=coords,
                    flow=flow,
                    selected_hubs=selected_hubs,
                    selected_routes=selected_routes,
                    output_path=str(image_path),
                    title="Solução SP - 11 regiões",
                )

        objective = None
        status = None
        runtime = None

        if model is not None:
            status = getattr(model, "Status", None)
            runtime = getattr(model, "Runtime", None)
            if getattr(model, "SolCount", 0) > 0:
                objective = getattr(model, "ObjVal", None)

        route_costs = []
        for (origin, destination), (first_hub, second_hub) in selected_routes.items():
            flow_value = flow[(origin, destination)]
            collection_cost = flow_value * route_c_col[(origin, first_hub)]
            inter_hub_cost = flow_value * route_c_hub[(first_hub, second_hub)]
            delivery_cost = flow_value * route_c_ent[(second_hub, destination)]
            route_costs.append({
                "origem": origin,
                "destino": destination,
                "uso de hubs": "Um hub" if first_hub == second_hub else "Dois hubs",
                "fluxo": flow_value,
                "pacotes coleta": flow_value if origin != first_hub else 0,
                "pacotes inter-hub": flow_value if first_hub != second_hub else 0,
                "pacotes entrega": flow_value if second_hub != destination else 0,
                "custo coleta": collection_cost,
                "custo inter-hub": inter_hub_cost,
                "custo entrega": delivery_cost,
                "custo total": collection_cost + inter_hub_cost + delivery_cost,
            })
        is_optimal = ( model is not None and model.Status == GRB.OPTIMAL and model.SolCount > 0)
        return {
            "ok": is_optimal and bool(selected_hubs),
            "log": buffer.getvalue(),
            "model_status": status,
            "runtime": runtime,
            "objective": objective,
            "gap": getattr(model, "MIPGap", None) if model is not None else None,
            "num_vars": getattr(model, "NumVars", None) if model is not None else None,
            "num_constraints": getattr(model, "NumConstrs", None) if model is not None else None,
            "selected_hubs": selected_hubs,
            "selected_routes": selected_routes,
            "route_costs": route_costs,
            "image_path": image_path,
            "elapsed": time.perf_counter() - started,
            "x_values": x_values,
            "d_acesso_col": data["d_acesso_col"],
            "d_acesso_ent": data["d_acesso_ent"],
            "d_interno_col": data["d_interno_col"],
            "d_interno_ent": data["d_interno_ent"],
            "flow": flow,
            "distance": distance,
            "params": data["params"],
        }
    except Exception as error:
        return {
            "ok": False,
            "log": buffer.getvalue(),
            "error": str(error),
            "elapsed": time.perf_counter() - started,
        }
    finally:
        os.chdir(previous_cwd)
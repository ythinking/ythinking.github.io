import argparse
from pathlib import Path

import numpy as np
import pandas as pd
import opendssdirect as dss
DSS_MODEL_PATH = Path(__file__).with_name("IEEE33_Modified_24h.dss")

def _load_dss(dss_path: Path):
    dss.Basic.ClearAll()
    # No spaces in the default path, but quoting doesn't hurt.
    dss.Text.Command(f'Compile "{str(dss_path)}"')
    dss.Text.Command("Set Mode=Daily")
    dss.Text.Command("Set StepSize=1h")
    dss.Text.Command("Set Number=1")


def _collect_static_topology():
    """
    After compile, read constant metadata (bus indices for each line; bus indices for each load).
    We later read only powers each time step.
    """
    # Lines: store (name, bus1, bus2)
    lines = []
    for lname in dss.Lines.AllNames():
        dss.Lines.Name(lname)
        bus1 = int(dss.Lines.Bus1())
        bus2 = int(dss.Lines.Bus2())
        lines.append((lname, bus1, bus2))

    # Loads: categorize by prefixes
    # Demand loads: LD_{bus}  (positive kW)
    # DER loads: PV_{bus}, WT_{bus}, DG_{bus}, ESS_{bus} (injection modeled as negative kW when discharging)
    demand_loads = []
    der_loads = []
    load_bus = {}
    load_type = {}

    for load_name in dss.Loads.AllNames():
        dss.Loads.Name(load_name)
        bus_names = dss.CktElement.BusNames()
        if not bus_names:
            continue
        bus = int(str(bus_names[0]))
        lname = load_name.lower()
        load_bus[load_name] = bus

        if lname.startswith("ld_"):
            demand_loads.append(load_name)
            load_type[load_name] = "demand"
        elif lname.startswith("pv_"):
            der_loads.append(load_name)
            load_type[load_name] = "pv"
        elif lname.startswith("wt_"):
            der_loads.append(load_name)
            load_type[load_name] = "wt"
        elif lname.startswith("dg_"):
            der_loads.append(load_name)
            load_type[load_name] = "dg"
        elif lname.startswith("ess_"):
            der_loads.append(load_name)
            load_type[load_name] = "ess"
        else:
            # Unknown load; ignore for carbon accounting.
            pass

    # Vsource (assume the grid source is the first one)
    vsource_names = dss.Vsources.AllNames()
    if not vsource_names:
        raise RuntimeError("No Vsource found in the compiled model.")
    vsource_name = vsource_names[0]

    return lines, demand_loads, der_loads, load_bus, load_type, vsource_name


def _get_line_flows(lines):
    """
    For each line, read terminal powers and return outgoing power contributions.
    Returns:
      edge_out: dict[(i,j)] = P_out_from_i_to_j_kW   (only non-negative outflows)
      out_sum: np.array shape (N,) = sum outgoing for each bus i
    """
    n_bus = 33
    edge_out = {}
    out_sum = np.zeros(n_bus)

    for lname, bus1, bus2 in lines:
        dss.Lines.Name(lname)
        # TotalPowers for line: [P1, Q1, P2, Q2] (P1 at terminal bus1 side, P2 at terminal bus2 side)
        tp = dss.CktElement.TotalPowers()
        if len(tp) < 4:
            continue
        P1 = float(tp[0])
        P2 = float(tp[2])

        # Power leaving terminal1 toward terminal2
        if P1 > 0:
            i, j = bus1, bus2
            edge_out[(i, j)] = edge_out.get((i, j), 0.0) + P1
            out_sum[i - 1] += P1

        # Power leaving terminal2 toward terminal1
        if P2 > 0:
            i, j = bus2, bus1
            edge_out[(i, j)] = edge_out.get((i, j), 0.0) + P2
            out_sum[i - 1] += P2

    return edge_out, out_sum


def _build_T_from_flows(edge_out, out_sum):
    n = 33
    T = np.zeros((n, n), dtype=float)
    for (i, j), p_out in edge_out.items():
        denom = out_sum[i - 1]
        if denom > 1e-9:
            T[i - 1, j - 1] = p_out / denom
    return T


def _read_load_powers(load_names):
    """
    Read each load's P (kW) via active CktElement.TotalPowers()[0].
    Returns dict[name] = P_kW
    """
    out = {}
    for name in load_names:
        dss.Loads.Name(name)
        tp = dss.CktElement.TotalPowers()
        if len(tp) < 2:
            out[name] = 0.0
        else:
            out[name] = float(tp[0])
    return out


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--dss",
        default=str(Path(__file__).with_name("IEEE33_Modified_24h.dss")),
        help="Path to the OpenDSS .dss model file.",
    )
    parser.add_argument(
        "--out",
        default=str(Path(__file__).with_name("node_carbon_timeseries.csv")),
        help="Output CSV path.",
    )
    parser.add_argument("--hours", type=int, default=24, help="Number of hours to simulate (starting at 0).")
    args = parser.parse_args()

    dss_path = Path(args.dss)
    out_csv = Path(args.out)
    if not dss_path.exists():
        raise FileNotFoundError(dss_path)

    # Carbon factors (kgCO2/kWh). These are placeholders for now.
    EF_GRID = 0.70
    EF_DG = 0.50
    EF_PV = 0.00
    EF_WT = 0.00
    EF_ESS = 0.70  # Simplified: treat ESS discharge as grid-carbon-mix.

    EF_BY_TYPE = {"grid": EF_GRID, "dg": EF_DG, "pv": EF_PV, "wt": EF_WT, "ess": EF_ESS}

    # Load model
    _load_dss(dss_path)
    lines, demand_loads, der_loads, load_bus, load_type, vsource_name = _collect_static_topology()

    n_bus = 33
    rows = []

    for hr in range(args.hours):
        dss.Text.Command(f"Set Hour={hr}")
        dss.Solution.Solve()

        # --- Build T ---
        edge_out, out_sum = _get_line_flows(lines)
        T = _build_T_from_flows(edge_out, out_sum)
        A = np.eye(n_bus) - T

        # --- Build S (carbon injection rates) ---
        S = np.zeros(n_bus, dtype=float)  # kgCO2/h
        injection = np.zeros(n_bus, dtype=float)  # kW injected from sources (for diagnostics)

        # DER sources (PV/WT/DG/ESS): injection occurs when load P is negative
        der_p = _read_load_powers(der_loads)
        for lname, P_kW in der_p.items():
            bus = load_bus[lname]
            p_inj = max(-P_kW, 0.0)  # kW
            if p_inj <= 0:
                continue
            ltype = load_type[lname]
            S[bus - 1] += p_inj * EF_BY_TYPE[ltype]
            injection[bus - 1] += p_inj

        # Grid source at bus 1:
        dss.Vsources.Name(vsource_name)
        tp_v = dss.CktElement.TotalPowers()
        # In OpenDSS, for import, the vsource terminal P is typically negative; injection is -P
        P_grid_inj = max(-float(tp_v[0]), 0.0) if len(tp_v) >= 1 else 0.0
        S[0] += P_grid_inj * EF_BY_TYPE["grid"]
        injection[0] += P_grid_inj

        # --- Solve for carbon potentials ---
        # Solve (I - T) C = S; use lstsq for stability.
        C = np.linalg.lstsq(A, S, rcond=1e-6)[0]  # kgCO2/h at each node

        # --- Demand energy (kW) for EF_node ---
        P_demand = np.zeros(n_bus, dtype=float)
        demand_p = _read_load_powers(demand_loads)
        for lname, P_kW in demand_p.items():
            bus = load_bus[lname]
            P_demand[bus - 1] += max(P_kW, 0.0)

        EF_node = np.zeros(n_bus, dtype=float)
        mask = P_demand > 1e-9
        EF_node[mask] = C[mask] / P_demand[mask]  # (kgCO2/h) / (kW) = kgCO2/kWh

        # --- Write outputs ---
        for bus in range(1, n_bus + 1):
            rows.append(
                {
                    "hour": hr,
                    "bus": bus,
                    "P_demand_kW": P_demand[bus - 1],
                    "C_kgCO2_per_h": C[bus - 1],
                    "EF_node_kgCO2_per_kWh": EF_node[bus - 1],
                    "P_source_inj_kW": injection[bus - 1],
                    "Tdiag_norm": float(np.mean(np.diag(T))) if hr == 0 else np.nan,
                }
            )

        print(f"[hour {hr:02d}] solved; max EF_node={EF_node.max():.4f} kgCO2/kWh")

    df = pd.DataFrame(rows)
    df.to_csv(out_csv, index=False, encoding="utf-8-sig")
    print(f"Saved: {out_csv}")


if __name__ == "__main__":
    main()


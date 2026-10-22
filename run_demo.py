"""

End-to-end demonstration of the V2X AI + blockchain trust framework.



    python run_demo.py              # headless emergency-spoofing demo in the terminal

    python run_demo.py --serve      # ... then start the API server for the dashboard

    python run_demo.py --retrain    # retrain the detector first



Flow shown: SUMO car -> claims to be an ambulance -> sends emergency V2X messages

-> neighbours receive them -> AI/rules detect the type inconsistency -> trust

drops -> smart contract records evidence on the blockchain -> alert -> the

neighbour's received-message history shows the flagged messages.

"""



import argparse

import logging

import os

import subprocess

import sys



from rich.console import Console

from rich.markup import escape

from rich.panel import Panel

from rich.table import Table



from config import get_config



if sys.platform == "win32":

    try:

        sys.stdout.reconfigure(encoding="utf-8")

        sys.stderr.reconfigure(encoding="utf-8")

    except Exception:

        pass



console = Console(width=140, legacy_windows=False)

ROOT = os.path.dirname(os.path.abspath(__file__))





def ensure_model(retrain: bool):

    model = os.path.join(get_config().ai.model_dir, "mbd_model.joblib")

    if retrain or not os.path.exists(model):

        console.print("[cyan]Training the misbehaviour detector (~3 min)…[/cyan]")

        subprocess.run([sys.executable, "-m", "ai.train_detector"], cwd=ROOT, check=True)

    else:

        console.print(f"[green]✓[/green] trained detector found ({model})")





def run(seconds_before: float, seconds_after: float):

    from backend.evidence import evidence_hash

    from backend.orchestrator import SimulationOrchestrator



    orch = SimulationOrchestrator(get_config())

    orch.setup("normal")

    orch.start()

    console.print(f"[green]✓[/green] traffic: {'mock grid model' if orch.mock_mode else 'SUMO (TraCI)'} · "

                  f"detector: {orch.detector.model_name} + rules")

    step = get_config().simulation.step_length

    with console.status("warming up traffic…"):

        for _ in range(int(seconds_before / step)):

            orch.step()



    attack = orch.launch_attack(None, "emergency_spoofing")

    vid = attack["vehicle_id"]

    console.print(Panel.fit(f"[bold]Vehicle {vid}[/bold] ({orch.vehicles[vid]['type']}) starts claiming to be an "

                            f"[bold red]{attack['params']['claimed_type']}[/bold red]", title="Attack launched"))

    with console.status("running the pipeline…"):

        for _ in range(int(seconds_after / step)):

            orch.step()



    comp = orch.attack_comparison(vid)

    t = Table(title="Before / after")

    for c in ("", "trust", "status", "claimed type", "on-chain reports"):

        t.add_column(c)

    b, a = comp["before"], comp["after"]

    t.add_row("before", f"{b['trust'] * 100:.1f}", b["status"], b["claimed_type"], str(b["on_chain_reports"]))

    t.add_row("after", f"{a['trust'] * 100:.1f}", a["status"], a["claimed_type"], str(a["on_chain_reports"]))

    console.print(t)

    det = comp["first_detection"]

    if det:

        console.print(f"Detected after [bold]{det['latency_s']:.1f} s[/bold] with probability {det['probability']:.1%}")



    th = Table(title=f"Trust history of {vid}")

    th.add_column("time"); th.add_column("trust"); th.add_column("reason")

    for e in orch.trust.history(vid):

        th.add_row(f"{e['time']:.1f}", f"{e['old_score'] * 100:.1f} → {e['new_score'] * 100:.1f}", escape(e["reason"]))

    console.print(th)



    for alert in list(orch.alerts)[:3]:

        console.print(f"🚨 [bold]{escape(alert['title'])}[/bold] {escape(alert['message'])}")



    ev_ids = comp["evidence_ids"]

    if ev_ids:

        rec = orch.evidence.get(ev_ids[0])

        ver = orch.contract.verify_evidence(rec["attack_id"], evidence_hash(rec))

        console.print(f"Evidence {rec['attack_id']}: expected [green]{rec['expected']}[/green], observed "

                      f"[red]{rec['observed']}[/red]; on-chain hash {'matches' if ver['valid'] else 'MISMATCH'} "

                      f"(tx {ver['tx_id']}, block {ver['block']})")



    receiver = next((r for r in orch.received if any(x[0]["sender"] == vid for x in orch.received[r])), None)

    if receiver:

        rt = Table(title=f"Received message history of {receiver} (from {vid})")

        for c in ("time", "sender", "type", "message", "status", "distance", "sender trust", "AI conf.", "tx"):

            rt.add_column(c)

        for m in orch.received_messages(receiver, sender=vid, limit=6)["messages"]:

            rt.add_row(f"{m['time']:.1f}", m["sender"], m["type"], escape(m["content"]), m["status"], f"{m['distance']:.0f} m",

                       f"{m['sender_trust'] * 100:.1f}", f"{m['ai_confidence']:.1%}", m["tx_id"] or "—")

        console.print(rt)

    sec = orch.get_stats()["security"]

    console.print(f"Messages analysed: {sec['true_positives'] + sec['false_positives'] + sec['true_negatives'] + sec['false_negatives']}"

                  f" · detection rate {sec['detection_rate']:.1%} · false-positive rate {sec['false_positive_rate']:.3%}"

                  f" · blocks {len(orch.chain.chain)}")

    orch.shutdown()





def main():

    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)

    parser.add_argument("--serve", action="store_true", help="start the API server after the demo")

    parser.add_argument("--retrain", action="store_true", help="retrain the detector first")

    parser.add_argument("--warmup", type=float, default=15.0)

    parser.add_argument("--duration", type=float, default=20.0)

    args = parser.parse_args()

    logging.basicConfig(level=logging.ERROR)



    console.print(Panel.fit("[bold cyan]V2X AI + Blockchain Trust Framework[/bold cyan]\nEmergency vehicle spoofing demo"))

    ensure_model(args.retrain)

    run(args.warmup, args.duration)



    if args.serve:

        console.print("\nStarting API on http://127.0.0.1:8000 — run the dashboard with "

                      "[bold]cd dashboard && npm run dev[/bold] and open http://localhost:5173")

        subprocess.run([sys.executable, "-m", "uvicorn", "backend.api:app", "--host", "127.0.0.1", "--port", "8000"], cwd=ROOT)





if __name__ == "__main__":

    main()

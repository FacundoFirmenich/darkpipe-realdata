"""DarkPipe command line interface."""
import argparse,json
from pathlib import Path
from .pipeline import run_live
from .provenance import write_bytes
from .sources import fetch_hapi

def main(argv=None):
    parser=argparse.ArgumentParser(prog="darkpipe",description="Real-data-first environmental foreground diagnostics");sub=parser.add_subparsers(dest="command",required=True)
    run=sub.add_parser("run");run.add_argument("--output",default="darkpipe_run");run.add_argument("--station",default="BOU");run.add_argument("--raw-retention",choices=("full","hash-only"),default="full")
    hapi=sub.add_parser("hapi");hapi.add_argument("--provider",choices=("intermagnet","nasa_cdaweb"),required=True);hapi.add_argument("--dataset",required=True);hapi.add_argument("--start",required=True);hapi.add_argument("--stop",required=True);hapi.add_argument("--output",required=True)
    args=parser.parse_args(argv)
    if args.command=="run": result=run_live(args.output,args.station,args.raw_retention=="full");print(json.dumps({"status":"ok","output":str(Path(args.output).resolve()),"rows":result["analysis"]["aligned_finite_rows"]}))
    else:
        source=fetch_hapi(args.provider,args.dataset,args.start,args.stop);target=Path(args.output);target.mkdir(parents=True,exist_ok=True);write_bytes(target/"info.json",source.artifacts[0].content);write_bytes(target/"data.json",source.artifacts[1].content);source.frame.to_csv(target/"data.csv",index=False);print(json.dumps({"status":"ok","rows":len(source.frame),"sha256":source.artifacts[1].sha256}))
if __name__=="__main__": main()

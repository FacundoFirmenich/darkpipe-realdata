from darkpipe.pipeline import run_live
if __name__=="__main__":
    report=run_live("darkpipe_run",station="BOU",retain_raw=True)
    print(report["analysis"]["jurisdiction"])

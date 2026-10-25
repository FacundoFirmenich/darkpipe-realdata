#!/usr/bin/env python3
import json, os, platform, sys
from importlib.util import find_spec

def main():
    providers={
      'jev': {'adapter_compiled':True,'live_executable':bool(os.getenv('TYPESAFE_API_KEY')),'blocker':None if os.getenv('TYPESAFE_API_KEY') else 'TYPESAFE_API_KEY_NOT_PRESENT'},
      'laya': {'adapter_compiled':True,'package_present':find_spec('laya') is not None,'live_executable':find_spec('laya') is not None,'blocker':None if find_spec('laya') else 'LAYA_PACKAGE_OR_WEIGHTS_NOT_PRESENT'},
      'nimble': {'adapter_compiled':True,'live_executable':False,'blocker':'9B_PROVIDER_REQUIRES_GPU_OR_REMOTE_ENDPOINT_NOT_CONFIGURED'},
      'bifrost_custom': {'adapter_compiled':True,'live_executable':bool(os.getenv('IRP27_DECISION_PROVIDER_URL')),'blocker':None if os.getenv('IRP27_DECISION_PROVIDER_URL') else 'CUSTOM_ENDPOINT_NOT_CONFIGURED'}
    }
    print(json.dumps({'python':sys.version,'platform':platform.platform(),'providers':providers,'automatic_execution':False,'automatic_publication':False},indent=2))
if __name__=='__main__': main()

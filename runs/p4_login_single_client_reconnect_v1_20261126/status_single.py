"""Serve the single-client run using the established local progress view."""
from http.server import ThreadingHTTPServer
from pathlib import Path
import sys

sys.path.insert(0,str(Path(__file__).resolve().parent.parent/"p4_login_legal_reconnect_v1_20261126"))
import status_reconnect as view

view.HTML = view.HTML.replace("合法重连压力复测","单客户端轮换合法重连压力")
view.HTML = view.HTML.replace('s.batch,s.scheduled_rate?', 's.batch,s.client?"客户端 "+s.client:"",s.scheduled_rate?')
ThreadingHTTPServer(("127.0.0.1",view.PORT),view.Handler).serve_forever()

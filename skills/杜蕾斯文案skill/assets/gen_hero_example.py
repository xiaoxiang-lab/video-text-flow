import os, json, time, urllib.request, concurrent.futures, re
KEY=os.environ.get("LUMINA_API_KEY") or open(os.path.expanduser("~/.lumina-api-key")).read().strip()
B="https://api.lk888.ai/v1"; OUT="hero5"; os.makedirs(OUT,exist_ok=True)
def post(p,d):
    r=urllib.request.Request(B+p,data=json.dumps(d).encode(),headers={"Authorization":"Bearer "+KEY,"Content-Type":"application/json"})
    return json.load(urllib.request.urlopen(r,timeout=180))
def get(p):
    r=urllib.request.Request(B+p,headers={"Authorization":"Bearer "+KEY})
    return json.load(urllib.request.urlopen(r,timeout=180))

BASE=("Top-down editorial still-life photograph on a seamless warm off-white paper background (#F1EBE0). "
 "SUBJECT: on one side, a single heavy chaotic tangled bundle of about forty old brass and silver keys on one "
 "overloaded keyring; separated from it by clear empty space, exactly ONE single clean elegant brass key lying alone. "
 "Soft directional key light from upper left, delicate natural shadows, fine film grain, muted expensive magazine aesthetic. "
 "Absolutely NO text, NO letters, NO numbers, NO logos, NO watermark, NO people, NO hands, NO props other than the keys.")

JOBS=[
 ("3x4","1920x2560", BASE+" COMPOSITION: both key groups sit in the LOWER two thirds of a tall vertical frame; "
   "the entire upper third is completely empty clean paper for typography."),
 ("1x1","2048x2048", BASE+" COMPOSITION: both key groups sit in the LOWER half of a square frame; "
   "the upper half is completely empty clean paper for typography."),
 ("4x3","2560x1920", BASE+" COMPOSITION: both key groups are pushed to the RIGHT half of a horizontal frame; "
   "the entire left half is completely empty clean paper for typography."),
 ("9x16","1440x2560", BASE+" COMPOSITION: both key groups sit in the LOWER 55 percent of a very tall vertical frame; "
   "the upper 45 percent is completely empty clean paper for typography."),
 ("16x9","2560x1440", BASE+" COMPOSITION: both key groups are pushed to the RIGHT 45 percent of a wide horizontal frame; "
   "the left 55 percent is completely empty clean paper for typography."),
]
def run(j):
    tag,size,prompt=j
    r=post("/media/generate",{"model":"gpt-image-2","params":{"prompt":prompt,"size":size}})
    tid=(r.get("data") or {}).get("task_id")
    if not tid: return tag,"submitfail "+json.dumps(r,ensure_ascii=False)[:200]
    for _ in range(220):
        time.sleep(5)
        try: s=get("/skills/task-status?task_id=%s"%tid)
        except Exception: continue
        d=s.get("data",s)
        if not d.get("is_final"): continue
        u=re.findall(r'https?://[^"\s\\]+\.(?:png|jpg|jpeg|webp)',json.dumps(d,ensure_ascii=False))
        if not u: return tag,"nourl"
        fp="%s/%s.png"%(OUT,tag); urllib.request.urlretrieve(u[0],fp); return tag,"OK "+fp
    return tag,"timeout"
with concurrent.futures.ThreadPoolExecutor(max_workers=5) as ex:
    for t,m in ex.map(run,JOBS): print(t,m,flush=True)

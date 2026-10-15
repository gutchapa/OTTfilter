import qrcode, json
links = {
 "instagram": "https://www.instagram.com/bodhanaandlearningtree/",
 "facebook":  "https://www.facebook.com/BodhanaandLearningTree/",
 "website":   "https://bodhana-learningtree.co.in/",
 "campuses":  "https://bodhana-learningtree.co.in/campuses",
}
out = {}
for k, url in links.items():
    q = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_M, border=0)
    q.add_data(url); q.make(fit=True)
    m = q.get_matrix(); n = len(m)
    d = "".join(f"M{x} {y}h1v1h-1z" for y,row in enumerate(m) for x,v in enumerate(row) if v)
    out[k] = {"n": n, "d": d, "url": url}
json.dump(out, open("qr.json","w"))
print({k:v["n"] for k,v in out.items()})

"""Mesure du temps de génération d'images par SD-Turbo sur CPU (non intégré à docgen).

  pip install torch --index-url https://download.pytorch.org/whl/cpu
  pip install diffusers transformers accelerate
  python banc/mesurer_sd_turbo.py
"""
import json
import resource
import time
from pathlib import Path

import torch
from diffusers import AutoPipelineForText2Image

torch.set_num_threads(4)
SORTIE = Path(__file__).resolve().parent / "resultats" / "sd_turbo"
SORTIE.mkdir(parents=True, exist_ok=True)
INVITES = ["a flat illustration of a community garden with vegetables, simple shapes",
           "an icon of a bicycle repair workshop, minimalist, white background"]

t0 = time.perf_counter()
pipe = AutoPipelineForText2Image.from_pretrained("stabilityai/sd-turbo", torch_dtype=torch.float32)
chargement = time.perf_counter() - t0
mesures = {"chargement_s": round(chargement, 1), "essais": []}
for taille in (512, 256):
    for etapes in (1, 4):
        for k, invite in enumerate(INVITES):
            t = time.perf_counter()
            img = pipe(invite, num_inference_steps=etapes, guidance_scale=0.0, height=taille, width=taille,
                       generator=torch.Generator().manual_seed(k)).images[0]
            dt = time.perf_counter() - t
            nom = f"{taille}px_{etapes}etapes_{k}.png"
            img.save(SORTIE / nom)
            mesures["essais"].append({"taille": taille, "etapes": etapes, "secondes": round(dt, 1), "image": nom})
            print(mesures["essais"][-1], flush=True)
mesures["memoire_max_mo"] = round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024)
(SORTIE / "mesures.json").write_text(json.dumps(mesures, indent=1))
print(mesures)

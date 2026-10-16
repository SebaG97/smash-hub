from pathlib import Path
print(Path("infra/digitalocean/app.yaml").read_text(encoding="utf-8"))
print(Path("infra/digitalocean/migration-job.yaml").read_text(encoding="utf-8"))

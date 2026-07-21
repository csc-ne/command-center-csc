# VM_SETUP — RTS em Ubuntu Server 22.04+

Guia passo-a-passo para subir o RTS numa VM Linux limpa. Ao final, o stack
deve subir sozinho no boot via systemd.

> Referência de SO: Ubuntu Server 22.04 LTS ou 24.04 LTS. Em outras distros
> (Debian, RHEL) a lógica é a mesma, ajustando o gerenciador de pacotes.

---

## 1. Provisionamento da VM

Requisitos mínimos para operação confortável:

- 2 vCPU
- 4 GB RAM
- 20 GB disco
- IP fixo na rede interna (recomendado) — facilita firewall do MySQL
- Acesso SSH com sudo

Porta liberadas no firewall (inbound):

| Porta | Origem                          | Uso                     |
| ----- | ------------------------------- | ----------------------- |
| 22    | rede admin                      | SSH                     |
| 5001  | rede interna                    | `/status` do rts-core   |
| 8080  | usuários do painel              | dashboard               |

Outbound:

- 443 → `graph.facebook.com` (WhatsApp), `*.googleapis.com` (Firebase),
  `sandboxapi.deere.com` (JD).
- 3306 → MySQL do host onde o bancovz está (se for remoto).

---

## 2. Bootstrap automático da VM

Clone o repositório em `/opt/rts` e rode o bootstrap:

```bash
sudo mkdir -p /opt && sudo chown $USER:$USER /opt
cd /opt
git clone <URL_DO_REPO> rts
cd rts
sudo bash docker/scripts/install-vm.sh
```

O script:

1. instala `docker-ce` + `docker-compose-plugin` (oficial da Docker)
2. habilita o serviço docker no boot
3. adiciona seu usuário ao grupo `docker`
4. ajusta timezone para `America/Recife`
5. instala utilitários (`curl`, `nc`, `jq`, `python3`)

Faça **logout/login** (ou `newgrp docker`) depois para aplicar o grupo.

---

## 3. Arquivos de segredo

Dois arquivos precisam existir **fora do git**:

### `/opt/rts/.env`

```bash
cp /opt/rts/docker/.env.example /opt/rts/.env
nano /opt/rts/.env           # preencher valores reais
chmod 600 /opt/rts/.env
```

Revisar especialmente:

- `IPDESKTOPDB` e `HOST_DB` — se o MySQL é no próprio host da VM, use
  `host.docker.internal`. Se for em outra máquina, coloque o IP real.
- `TKWPP` — pode estar vazio/vencido; o WppTokenManager renova em tempo
  de execução.
- `APP_ID`, `APP_SECRET`, `WPP_ACCOUNT_ID` — **obrigatórios** para que a
  renovação automática funcione.
- `REFRESH_TOKEN` (JD) — obtido manualmente via GUI na primeira vez.
  A renovação continua automática dali em diante.

### `/opt/rts/connection/serviceAccount.json`

Copiar do gerenciador de segredos (ou do console do Firebase). Não
commitar no git.

```bash
chmod 600 /opt/rts/connection/serviceAccount.json
```

---

## 4. Preflight

```bash
cd /opt/rts/docker/scripts
bash preflight.sh
```

Saída esperada: todas as linhas `[OK]` e exit 0. Ajuste os `[ERRO]`
antes de prosseguir.

---

## 5. Build e primeiro up

```bash
bash build.sh              # ~3-5 min na primeira vez
bash up.sh                 # -d, detached
bash status.sh             # conferir
```

Logs de sanidade (`bash logs.sh rts-core`) devem mostrar, em sequência:

```
[INFO] rts.core: RTS-CORE (headless) iniciando...
[INFO] rts.core: Janela de expediente: 08:00–17:50 (Seg,Ter,Qua,Qui,Sex)
[INFO] rts.core: Status HTTP escutando em 0.0.0.0:5001 (/status, /healthz)
[INFO] <token_wpp>: Token WPP renovado com sucesso.
[INFO] <rts.main>: [EXPEDIENTE] Fora do horário ...   (se estiver fora)
```

Checagem dos endpoints:

```bash
curl -s http://localhost:5001/status | jq
curl -s -o /dev/null -w "%{http_code}\n" http://localhost:8080/
```

---

## 6. Auto-start no boot (systemd)

```bash
sudo cp /opt/rts/docker/systemd/rts.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now rts.service
sudo systemctl status rts
```

- `sudo systemctl restart rts` — derruba e sobe novamente.
- `sudo systemctl reload rts` — `docker compose pull` + `up -d` (útil
  quando a imagem muda).
- `sudo journalctl -u rts -f` — logs do compose (não do container).
  Para logs da aplicação, continue usando `bash logs.sh`.

---

## 7. Rotina de atualização

```bash
cd /opt/rts
git pull
cd docker/scripts
bash build.sh              # rebuild (layers de código mudam; deps em cache)
sudo systemctl restart rts # ou: bash down.sh && bash up.sh
bash status.sh
```

Se mudou só o painel web, pode-se atualizar apenas um serviço:

```bash
docker compose -f /opt/rts/docker/docker-compose.yml up -d --build rts-dashboard
```

---

## 8. Observabilidade mínima recomendada

- `docker stats` — CPU/mem por container (script `status.sh` mostra).
- `docker logs --since=1h rts-core` — janela curta de eventos.
- Log rotation já está configurado no compose (`max-size: 10m`,
  `max-file: 5` → ~50 MB por serviço).
- Para centralizar, apontar o driver `logging` para `journald`, `syslog`
  ou um coletor externo (Loki, Datadog). Default atual: `json-file`.

---

## 9. Plano de rollback

Antes de subir uma nova versão em produção:

```bash
docker tag rts-core:latest rts-core:backup-$(date +%F)
docker tag rts-dashboard:latest rts-dashboard:backup-$(date +%F)
```

Se a nova versão falhar:

```bash
docker tag rts-core:backup-YYYY-MM-DD rts-core:latest
docker tag rts-dashboard:backup-YYYY-MM-DD rts-dashboard:latest
bash down.sh && bash up.sh
```

---

## 10. Checklist pós-deploy

- [ ] `rts-core` e `rts-dashboard` com status `healthy` em `docker compose ps`
- [ ] `/status` responde `{"status":"ON", "headless":true, ...}`
- [ ] `/healthz` responde `200 ok`
- [ ] `bash logs.sh rts-core` mostra renovação de token sem erros
- [ ] Alerta real chegou no WhatsApp (teste em horário comercial)
- [ ] Painel (`/`) abre e conecta ao Firebase (ver console do browser)
- [ ] `sudo systemctl is-enabled rts` → `enabled`
- [ ] Reboot da VM → stack sobe sozinho em até 1 min

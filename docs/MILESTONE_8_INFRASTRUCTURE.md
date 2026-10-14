# Milestone 8: Infrastructure Assistant

ATHENA can ask the local infrastructure tools for status. The commands are read-only.

## Commands

```text
/infra
/docker
/k8s
/jenkins
/openstack
```

From the terminal:

```bash
python3 scripts/athena_infra.py status
```

A missing command is reported and skipped. Docker Desktop can stay closed on an 8 GB machine.

## Jenkins

Set the address in the environment or in `.env`:

```bash
ATHENA_JENKINS_URL=http://127.0.0.1:8080
ATHENA_JENKINS_USER=your-user
ATHENA_JENKINS_TOKEN=your-token
```

The token is sent as basic auth and is not printed. Leave the token out of Git. `.env` is gitignored.

## What These Commands Do

- Docker: `docker ps`
- Kubernetes: `kubectl get pods -A`
- Jenkins: the job name and color from the JSON API
- OpenStack: `openstack server list`

They do not create, delete, restart, or resize anything.

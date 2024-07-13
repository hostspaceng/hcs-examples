from fastapi import FastAPI, HTTPException
from fastapi.openapi.docs import get_swagger_ui_html
from pydantic import BaseModel
import os
import yaml
import sentry_sdk
import requests
from bs4 import BeautifulSoup
import uuid
import json

sentry_sdk.init(
    dsn="https://99469ea4c40e9fb99e2b1cf9ecfa8fa7@o4507554427895808.ingest.de.sentry.io/4507578012532816",
    traces_sample_rate=1.0,
    profiles_sample_rate=1.0,
)

app = FastAPI()

class TraefikConfig(BaseModel):
    domain: str
    port: int
    container_name: str

    class Config:
        schema_extra = {
            "example": {
                "domain": "newdomain.hostspacecloud.com",
                "port": 4000,
                "container_name": "myapp"
            }
        }

class InviteRequest(BaseModel):
    email: str

    class Config:
        schema_extra = {
            "example": {
                "email": "user@example.com"
            }
        }

DYNAMIC_CONFIG_DIR = os.getenv("TRAEFIK_DYNAMIC_CONFIG_DIR", "/data/coolify/proxy/dynamic/")

def reload_traefik():
    os.system("docker restart coolify-proxy")

def add_domain_to_traefik(config: TraefikConfig):
    dynamic_config_path = os.path.join(DYNAMIC_CONFIG_DIR, f"{config.domain}.yaml")
    
    dynamic_config = {
        "http": {
            "middlewares": {
                "redirect-to-https": {
                    "redirectscheme": {
                        "scheme": "https"
                    }
                },
                "gzip": {
                    "compress": True
                }
            },
            "routers": {
                f"{config.container_name}-http": {
                    "middlewares": ["redirect-to-https"],
                    "entryPoints": ["http"],
                    "service": config.container_name,
                    "rule": f"Host(`{config.domain}`)"
                },
                f"{config.container_name}-https": {
                    "entryPoints": ["https"],
                    "service": config.container_name,
                    "rule": f"Host(`{config.domain}`)",
                    "tls": {
                        "certresolver": "letsencrypt"
                    }
                }
            },
            "services": {
                config.container_name: {
                    "loadBalancer": {
                        "servers": [
                            {"url": f"http://{config.container_name}:{config.port}"}
                        ]
                    }
                }
            }
        }
    }

    with open(dynamic_config_path, 'w') as f:
        yaml.dump(dynamic_config, f, default_flow_style=False)

    reload_traefik()

@app.post("/add-domain/")
def add_domain(config: TraefikConfig):
    try:
        add_domain_to_traefik(config)
        return {"message": "Domain added successfully!"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/invite/")
def invite_user(request: InviteRequest):
    try:
        # Initialize a session
        session = requests.Session()

        # URLs
        base_url = 'https://app-dev.hostspaceng.com'
        csrf_url = f'{base_url}/team/members'
        api_url = f'{base_url}/livewire/update'

        # Step 1: Fetch the CSRF token
        response = session.get(csrf_url)

        # Check for a successful response before proceeding
        if response.status_code != 200:
            raise Exception(f"Failed to fetch CSRF token. Status code: {response.status_code}")

        soup = BeautifulSoup(response.text, 'html.parser')
        csrf_token = soup.find('meta', {'name': 'csrf-token'})['content']

        # Generate unique IDs
        component_id = str(uuid.uuid4()).replace('-', '')[:16]
        checksum = str(uuid.uuid4()).replace('-', '')[:64]

        # Headers
        headers = {
            'accept': '*/*',
            'accept-language': 'en-US,en;q=0.9',
            'content-type': 'application/json',
            'origin': base_url,
            'referer': csrf_url,
            'sec-ch-ua': '"Not/A)Brand";v="8", "Chromium";v="126", "Google Chrome";v="126"',
            'sec-ch-ua-mobile': '?1',
            'sec-ch-ua-platform': '"Android"',
            'sec-fetch-dest': 'empty',
            'sec-fetch-mode': 'cors',
            'sec-fetch-site': 'same-origin',
            'user-agent': 'Mozilla/5.0 (Linux; Android 6.0; Nexus 5 Build/MRA58N) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Mobile Safari/537.36',
            'x-csrf-token': csrf_token,
            'x-livewire': '',
            'x-socket-id': '2992541043.271918350'  # This should be dynamically generated or fetched if required
        }

        # Payload for inviting a user
        email = request.email
        payload = {
            "_token": csrf_token,
            "components": [
                {
                    "snapshot": json.dumps({
                        "data": {
                            "email": "",
                            "role": "member"
                        },
                        "memo": {
                            "id": component_id,
                            "name": "team.invite-link",
                            "path": "team/members",
                            "method": "GET",
                            "children": [],
                            "scripts": [],
                            "assets": [],
                            "errors": [],
                            "locale": "en"
                        },
                        "checksum": checksum
                    }),
                    "updates": {"email": email},
                    "calls": [
                        {
                            "path": "",
                            "method": "viaLink",
                            "params": []
                        }
                    ]
                }
            ]
        }

        # Step 2: Make the API call with the fresh CSRF token
        response = session.post(api_url, headers=headers, json=payload)

        # Check the response
        if response.status_code == 200:
            return {"message": "User invited successfully!"}
        else:
            raise Exception(f"Error inviting user. Status code: {response.status_code}, Response Body: {response.text}")

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/", include_in_schema=False)
async def root():
    return get_swagger_ui_html(openapi_url=app.openapi_url, title="HostSpaceCloud Custom Domain Mapping")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

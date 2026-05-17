# Nvidia Ollama Proxy

Proxy que convierte llamadas Ollama API → Nvidia AI Foundation Models API. Permite usar modelos de Nvidia (Nemotron, Llama, Mistral, DeepSeek, GLM, MiniMax) con cualquier cliente que soporte Ollama (como Open WebUI, Docker Ollama, etc.).

## Características / Features

- **Traduce API Ollama → Nvidia**: Compatible con endpoints `/api/chat`, `/api/chat/completions`, `/v1/chat/completions`
- **12+ modelos disponibles**: Nemotron, Llama 3.1/3.3, Mistral Large 3, DeepSeek V4, GLM-5.1, MiniMax M2.7...
- **Soporta imágenes**: Para modelos vision (Nemotron Nano 12B VL)
- **Reintentos automáticos**: Hasta 3 intentos con backoff exponencial si Nvidia responde vacío
- **Forza non-streaming**: Evita problemas de streaming con la API de Nvidia

## Modelos disponibles / Available Models

| Modelo | Nvidia ID | Tipo |
|--------|-----------|------|
| nemotron-3-super-120b | nvidia/nemotron-3-super-120b-a12b | Reasoning |
| nemotron-nano-12b-vl | nvidia/nemotron-nano-12b-v2-vl | Vision |
| llama-3.1-70b | meta/llama-3.1-70b-instruct | Chat |
| llama-3.1-8b | meta/llama-3.1-8b-instruct | Chat |
| llama-3.3-70b | meta/llama-3.3-70b-instruct | Chat |
| mistral-large-3 | mistralai/mistral-large-3-675b-instruct-2512 | Chat |
| mistral-7b | mistralai/mistral-7b-instruct-v0.3 | Chat |
| deepseek-v4-flash | deepseek-ai/deepseek-v4-flash | Chat |
| glm-5.1 | z-ai/glm-5.1 | Chat |
| minimax-m2.7 | minimaxai/minimax-m2.7 | Chat |
| llama3 | meta/llama-3.1-70b-instruct | Alias |
| llama3.1 | meta/llama-3.1-70b-instruct | Alias |

## Instalación / Installation

```bash
# Clonar o copiar el script
git clone https://github.com/polidisio/nvidia-ollama-proxy.git
cd nvidia-ollama-proxy

# Instalar dependencias (solo Python estándar, no necesita libs externas)
pip install flask  # Opcional, solo si quieres el wrapper web

# Ejecutar
python3 nvidia_ollama_proxy.py --port 11435
```

## Configuración / Configuration

Edita las primeras líneas del script para cambiar la API key de Nvidia:

```python
NVIDIA_API_KEY = "nvapi-TU-API-KEY-AQUI"
NVIDIA_BASE_URL = "https://integrate.api.nvidia.com/v1"
```

## Uso con Open WebUI

### 1. Arrancar el proxy
```bash
python3 nvidia_ollama_proxy.py --port 11435
```

### 2. Configurar Open WebUI

Si usas Docker:
```bash
docker run -d \
  --name open-webui \
  -p 3000:8080 \
  -e OLLAMA_BASE_URL=http://TU_IP:11435 \
  -e USE_OLLAMA_DOCKER=false \
  ghcr.io/open-webui/open-webui:main
```

Si ya tienes Open WebUI ejecutándose, cambia `OLLAMA_BASE_URL` para que apunte al proxy.

### 3. Usar
Abre http://tu-ip:3000, crea una cuenta y selecciona el modelo que quieras de la lista.

## Uso directo / Direct Usage

```bash
# Listar modelos
curl http://localhost:11435/api/tags

# Chatear (formato Ollama)
curl -X POST http://localhost:11435/api/chat \
  -H "Content-Type: application/json" \
  -d '{
    "model": "nemotron-3-super-120b",
    "messages": [{"role": "user", "content": "Hola"}],
    "max_tokens": 100
  }'

# Chatear (formato OpenAI)
curl -X POST http://localhost:11435/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "llama-3.1-70b",
    "messages": [{"role": "user", "content": "Hello"}],
    "max_tokens": 50
  }'
```

## Servicio systemd (auto-arranque)

```ini
[Unit]
Description=Nvidia Ollama Proxy
After=network.target

[Service]
Type=simple
User=TU_USUARIO
ExecStart=/usr/bin/python3 /ruta/nvidia_ollama_proxy.py --port 11435
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl enable nvidia-proxy
sudo systemctl start nvidia-proxy
```

## Añadir nuevos modelos

Edita `MODEL_MAP` al inicio del script:

```python
MODEL_MAP = {
    "mi-modelo": "propietario/mi-modelo-id",
    # ...
}
```

## Solución de problemas / Troubleshooting

### "Nvidia returned invalid JSON"
- El proxy ya tiene reintentos automáticos
- Si persiste, Nvidia puede estar con rate limiting — espera 30s

### "Connection error" desde Open WebUI
- Verifica que el proxy está corriendo: `curl http://localhost:11435/api/tags`
- Verifica que Open WebUI apunta a la IP correcta del proxy

### Empty response from Nvidia
- Ocurre cuando hay rate limiting
- El proxy reintenta automáticamente hasta 3 veces

## Requisitos

- Python 3.8+
- Cuenta en Nvidia AI Foundation Models (API key)
- Red que permita conexión saliente a `integrate.api.nvidia.com:443`

## Licencia / License

MIT - Usa libre, mejora libre.

---

## English Version

### What is this?

A proxy that translates Ollama API calls to Nvidia AI Foundation Models API. It lets you use Nvidia-hosted models (like Nemotron, Llama, Mistral, DeepSeek, GLM, MiniMax) through any Ollama-compatible client (Open WebUI, etc.).

### Quick Start

```bash
git clone https://github.com/polidisio/nvidia-ollama-proxy.git
cd nvidia-ollama-proxy
# Edit the API key at the top of the script
python3 nvidia_ollama_proxy.py --port 11435
```

### API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/tags` | List available models |
| POST | `/api/chat` | Ollama chat completion |
| POST | `/api/chat/completions` | Ollama chat (alt path) |
| POST | `/v1/chat/completions` | OpenAI-compatible |
| GET | `/` | Health check |

### Why?

You want to use Open WebUI locally but run the models on Nvidia's servers. This proxy acts as a local Ollama instance and forwards requests to Nvidia.
#!/usr/bin/env python3
import json, re, sys, time
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen

ROOT = Path(__file__).parent
HTML = ROOT / 'index.html'
STATUS = ROOT / 'stock_status.json'
MAPPING = ROOT / 'stock_products.json'

def fetch(url):
    req = Request(url, headers={'User-Agent': 'DualRobotics-stock-check/1.0'})
    with urlopen(req, timeout=25) as r:
        text = r.read().decode('utf-8', 'replace')
    if re.search(r'(?i)agotad[oa]|sin\s+stock|no\s+disponible', text):
        return 0
    m = re.search(r'(?i)Disponibles?\s*:\s*(?:<[^>]+>\s*)*([0-9]+)', text)
    if not m:
        raise ValueError('No se pudo identificar el inventario')
    return int(m.group(1))

def main():
    mapping = json.loads(MAPPING.read_text())
    old = json.loads(STATUS.read_text()) if STATUS.exists() else {'products': {}}
    result = dict(old)
    result['provider'] = 'CVR Electrónica'
    result['updated_at'] = datetime.now(timezone.utc).isoformat()
    errors = []
    for pid, cfg in mapping.items():
        stocks = []
        try:
            for url in cfg['urls']:
                stocks.append(fetch(url))
                time.sleep(0.4)
            stock = min(stocks) if cfg.get('require_all') else max(stocks)
            result.setdefault('products', {})[pid] = {'status': 'agotado' if stock == 0 else ('pocas' if stock <= 5 else 'disponible'), 'stock': stock}
        except Exception as exc:
            errors.append(f'{pid}: {exc}')
    if errors:
        result['errors'] = errors
        print('Advertencias; se conservaron los estados anteriores de:', ', '.join(errors))
    else:
        result.pop('errors', None)
    STATUS.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    html = HTML.read_text()
    # Reemplaza la línea completa de cada producto para evitar duplicar
    # los campos de stock en ejecuciones posteriores.
    lines = []
    for line in html.splitlines():
        for pid, data in result.get('products', {}).items():
            pattern = rf'^(\s*)\{{id:{re.escape(pid)},\s*(.*?desc:"[^\"]*").*$'
            match = re.match(pattern, line)
            if match:
                line = f'{match.group(1)}{{id:{pid}, {match.group(2)}, stockStatus:"{data["status"]}", stock:{int(data.get("stock", 0))}}},'
                break
        lines.append(line)
    HTML.write_text("\n".join(lines) + "\n")
    print(f'Actualizados {len(result.get("products", {}))} productos. Errores: {len(errors)}')

if __name__ == '__main__':
    main()

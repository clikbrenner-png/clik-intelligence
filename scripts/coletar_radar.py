"""Coleta conservadora de indícios públicos; não confirma vagas, datas ou lucro."""
import json
import re
import hashlib
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FEED = ROOT / 'radar.json'
QUERIES = [
    'corrida de rua 2027 "Campos do Jordão"',
    'corrida de rua 2027 "Taubaté"',
    'corrida de rua 2027 "Pindamonhangaba"',
    'trail running 2027 "São Bento do Sapucaí"',
    'corrida ciclismo MTB 2027 "Vale do Paraíba"',
    'corrida 2027 "São José dos Campos"',
    'romaria peregrinação corrida 2027 "Aparecida"',
    'corrida 2027 "Gonçalves" MG',
]
# Distâncias aproximadas rodoviárias: apenas para triagem, não para calcular custos.
CITIES = [
    ('são bento do sapucaí', 'São Bento do Sapucaí', 0),
    ('campos do jordão', 'Campos do Jordão', 25),
    ('taubaté', 'Taubaté', 65),
    ('pindamonhangaba', 'Pindamonhangaba', 55),
    ('são josé dos campos', 'São José dos Campos', 100),
    ('aparecida', 'Aparecida', 85),
    ('gonçalves', 'Gonçalves', 35),
    ('vale do paraíba', 'Vale do Paraíba (local não definido)', None),
]
SPORT = re.compile(r'corrida|trail|maratona|ciclismo|ciclista|mtb|mountain bike|romaria|peregrina|ultramaratona', re.I)
YEAR = re.compile(r'\b202[6-9]\b')

def get(url):
    req = urllib.request.Request(url, headers={'User-Agent':'ClikBrennerRadar/0.4 (+public RSS research)'})
    with urllib.request.urlopen(req, timeout=18) as response:
        return response.read(2_000_000)

def existing():
    try:
        data = json.loads(FEED.read_text(encoding='utf-8'))
        return [x for x in data.get('events', []) if isinstance(x, dict)]
    except (FileNotFoundError, ValueError):
        return []

def main():
    now = datetime.now(timezone.utc)
    old = {x['id']:x for x in existing() if isinstance(x.get('id'), str)}
    found = {}
    errors = []
    for query in QUERIES:
        url = 'https://news.google.com/rss/search?' + urllib.parse.urlencode({'q':query,'hl':'pt-BR','gl':'BR','ceid':'BR:pt-419'})
        try:
            xml = ET.fromstring(get(url))
            for item in xml.findall('.//channel/item')[:25]:
                title = (item.findtext('title') or '').strip()
                link = (item.findtext('link') or '').strip()
                description = re.sub('<[^>]*>', ' ', item.findtext('description') or '')
                combined = (title+' '+description).casefold()
                if not SPORT.search(combined) or not YEAR.search(combined):
                    continue
                matches = [(city,km) for needle,city,km in CITIES if needle in combined]
                if not matches or not link.startswith('https://'):
                    continue
                city,km = matches[0]
                key = hashlib.sha256((title.casefold()+'|'+city.casefold()).encode()).hexdigest()[:16]
                found[key] = {
                    'id': key, 'name': title[:110], 'date': '', 'type':'Evento esportivo (a verificar)',
                    'city':city, 'distance':km, 'participants':None,
                    'revenue':None, 'cost':None, 'deadline':'', 'platform':'Não verificada',
                    'url':link, 'confidence':'low',
                    'notes':'INDÍCIO em notícia pública; não confirma realização futura, data, inscrição ou vaga de fotógrafo. Verifique a fonte oficial antes de contatar. Consulta: '+now.strftime('%d/%m/%Y')
                }
        except Exception as exc:
            errors.append(f'{query}: {type(exc).__name__}: {exc}')
    # Preserva indícios existentes por até 30 dias se as fontes falharem temporariamente.
    for key, value in old.items():
        if key not in found and value.get('origin') != 'manual':
            found[key] = value
    items = list(found.values())[:150]
    payload = {'updated_at':now.isoformat(), 'events':items,
               'note':'Resultados são indícios de notícias; nenhuma vaga, data ou lucro foi confirmado automaticamente.',
               'sources':'Google News RSS; fontes originais devem ser verificadas',
               'search_errors':errors[:15]}
    FEED.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(f'Indícios no feed: {len(items)}; erros de consulta: {len(errors)}')
    for error in errors: print('AVISO:', error)

if __name__ == '__main__':
    main()


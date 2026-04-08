from twitter import post_events
import json

# Simule une date d'arrivee connue
with open('dates.json', 'w') as f:
    json.dump({'Mme MARTIN Sophie': '2024-09-15'}, f)

fake_events = [
    {'type': 'arrivee', 'collaborateur': 'M. DUPONT Jean', 'senateur': 'M. PERRIN Cedric'},
    {'type': 'depart', 'collaborateur': 'Mme MARTIN Sophie', 'senateur': 'M. KANNER Patrick'},
]

fake_info = {
    'PERRIN CEDRIC': {'groupe': 'Les Republicains', 'departement': 'Territoire de Belfort'},
    'KANNER PATRICK': {'groupe': 'Socialiste', 'departement': 'Nord'},
}

post_events(fake_events, fake_info)
print('Done!')
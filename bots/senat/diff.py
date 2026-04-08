def compute_diff(old: dict, new: dict) -> list:
    events = []
    old_index = {c: s for s, collabs in old.items() for c in collabs}
    new_index = {c: s for s, collabs in new.items() for c in collabs}
    all_collabs = set(old_index) | set(new_index)
    for collab in all_collabs:
        old_sen = old_index.get(collab)
        new_sen = new_index.get(collab)
        if old_sen == new_sen:
            continue
        if old_sen and new_sen:
            events.append({"type": "transfert", "collaborateur": collab, "from": old_sen, "to": new_sen})
        elif old_sen and not new_sen:
            events.append({"type": "départ", "collaborateur": collab, "senateur": old_sen})
        elif not old_sen and new_sen:
            events.append({"type": "arrivée", "collaborateur": collab, "senateur": new_sen})
    return events

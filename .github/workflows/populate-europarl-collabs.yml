name: Populate Europarl — Collabs (Phase 2)

# Lancement manuel uniquement. dry_run=true par défaut.
on:
  workflow_dispatch:
    inputs:
      dry_run:
        description: "Mode dry-run (ne rien écrire en base)"
        type: boolean
        default: true
      limit:
        description: "Limiter à N MEPs (vide = tous, 81)"
        type: string
        default: ""
      max_changes:
        description: "Circuit breaker : max de mandats créés"
        type: string
        default: "2000"
      workers:
        description: "Threads de fetch en parallèle (3 par défaut)"
        type: string
        default: "3"

jobs:
  populate:
    runs-on: ubuntu-latest

    steps:
      - name: Checkout
        uses: actions/checkout@v4

      - name: Setup Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.11"
          cache: pip

      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install -r requirements.txt

      - name: Run populate_collabs
        env:
          SUPABASE_V2_URL: ${{ secrets.SUPABASE_V2_URL }}
          SUPABASE_V2_SERVICE_ROLE_KEY: ${{ secrets.SUPABASE_V2_SERVICE_ROLE_KEY }}
        run: |
          ARGS=""
          if [ "${{ inputs.dry_run }}" = "true" ]; then
            ARGS="$ARGS --dry-run"
          fi
          if [ -n "${{ inputs.limit }}" ]; then
            ARGS="$ARGS --limit ${{ inputs.limit }}"
          fi
          if [ -n "${{ inputs.max_changes }}" ]; then
            ARGS="$ARGS --max-changes ${{ inputs.max_changes }}"
          fi
          if [ -n "${{ inputs.workers }}" ]; then
            ARGS="$ARGS --workers ${{ inputs.workers }}"
          fi
          echo "Lancement avec args :$ARGS"
          python -m bots.europarl.populate_collabs $ARGS

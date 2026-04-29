-- ============================================================================
-- Migration v2_views.sql — vue helper pour la Phase 2+
-- À exécuter dans le SQL Editor du projet Supabase V2 avant de lancer
-- la Phase 2 (alimentation des collaborateurs).
-- ============================================================================

CREATE OR REPLACE VIEW v_elus_actifs_famille AS
SELECT
  e.id              AS elu_id,
  e.chambre_code,
  e.an_id,
  e.matricule_senat,
  e.ep_id,
  e.nom             AS elu_nom,
  e.prenom          AS elu_prenom,
  me.id             AS mandat_elu_id,
  me.date_debut     AS mandat_debut,
  me.groupe_id,
  gp.sigle          AS groupe_sigle,
  gp.label          AS groupe_label,
  gp.famille_id,
  fp.code           AS famille_code,
  fp.label          AS famille_label
FROM elus e
INNER JOIN mandats_elus me
  ON me.elu_id = e.id AND me.date_fin IS NULL
LEFT  JOIN groupes_politiques gp  ON gp.id = me.groupe_id
LEFT  JOIN familles_politiques fp ON fp.id = gp.famille_id
WHERE e.statut = 'actif';


-- Policy RLS pour rendre la vue lisible par anon (cohérent avec elus + mandats_elus)
-- Note : les vues héritent des RLS des tables sous-jacentes en Postgres,
-- donc cette policy n'est pas strictement nécessaire si les tables sont déjà
-- ouvertes à anon (ce qui est notre cas). Mais on la met explicitement pour clarté.

-- Pas de CREATE POLICY ici : les vues n'ont pas leur propre RLS, elles héritent
-- des tables sous-jacentes. Comme elus et mandats_elus sont déjà ouverts à anon,
-- la vue l'est aussi.

-- Regras das migrações:
--   1. Toda migração nova usa IF NOT EXISTS / IF EXISTS onde aplicável (schema e
--      objetos auxiliares), para ser segura em reexecução e em startup multi-processo.
--   2. Migração já aplicada NÃO se edita — schema_migrations controla por nome de
--      arquivo; correção ou evolução vira arquivo novo (NNN_*.sql) na sequência.

-- Índice de período: consultas por created_at em document_versions faziam scan sequencial.
CREATE INDEX IF NOT EXISTS idx_document_versions_created_at ON document_versions (created_at);

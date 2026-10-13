CREATE TABLE IF NOT EXISTS agent_document (
  collection VARCHAR(80) NOT NULL,
  id VARCHAR(200) NOT NULL,
  body CLOB NOT NULL,
  PRIMARY KEY(collection,id)
);

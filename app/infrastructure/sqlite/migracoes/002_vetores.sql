-- SAD-GD — vetores densos (sqlite-vec, ADR-006). bge-m3 = 1024 dimensões, distância cosseno.
-- Requer a extensão sqlite-vec carregada na conexão (feito por app.infrastructure.sqlite.conexao).

CREATE VIRTUAL TABLE trechos_vec USING vec0(
    trecho_id INTEGER PRIMARY KEY,
    embedding float[1024] distance_metric=cosine
);

CREATE VIRTUAL TABLE decisoes_vec USING vec0(
    decisao_id INTEGER PRIMARY KEY,
    embedding float[1024] distance_metric=cosine
);

CREATE VIRTUAL TABLE cache_semantico_vec USING vec0(
    cache_id INTEGER PRIMARY KEY,
    embedding float[1024] distance_metric=cosine
);

-- remove vetores órfãos quando o trecho/decisão/cache é apagado
CREATE TRIGGER trechos_vec_ad AFTER DELETE ON trechos BEGIN
    DELETE FROM trechos_vec WHERE trecho_id = old.id;
END;
CREATE TRIGGER decisoes_vec_ad AFTER DELETE ON decisoes BEGIN
    DELETE FROM decisoes_vec WHERE decisao_id = old.id;
END;
CREATE TRIGGER cache_semantico_vec_ad AFTER DELETE ON cache_semantico BEGIN
    DELETE FROM cache_semantico_vec WHERE cache_id = old.id;
END;

-- Test implementatie van Analytics Database-driven approach
-- Run deze queries in Supabase om de tabellen aan te maken en data te migreren

-- 1. Maak de tabellen aan (simpele versie met alleen organization_id)
-- Stopwoorden tabel
CREATE TABLE public.analytics_stopwords (
    stopword_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    word character varying(100) NOT NULL,
    organization_id integer NOT NULL DEFAULT 1,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT analytics_stopwords_organization_id_fkey FOREIGN KEY (organization_id) REFERENCES public.organization(organization_id),
    CONSTRAINT analytics_stopwords_unique_word_org UNIQUE (word, organization_id)
);

-- Sentiment woorden tabel (positief en negatief)
CREATE TABLE public.analytics_sentiment_words (
    sentiment_word_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    word character varying(100) NOT NULL,
    sentiment_type character varying(10) NOT NULL CHECK (sentiment_type IN ('positief', 'negatief')),
    organization_id integer NOT NULL DEFAULT 1,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT analytics_sentiment_words_organization_id_fkey FOREIGN KEY (organization_id) REFERENCES public.organization(organization_id),
    CONSTRAINT analytics_sentiment_words_unique_word_type_org UNIQUE (word, sentiment_type, organization_id)
);

-- Topic categorieën tabel
CREATE TABLE public.analytics_topic_categories (
    topic_category_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    category_name character varying(100) NOT NULL,
    organization_id integer NOT NULL DEFAULT 1,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT analytics_topic_categories_organization_id_fkey FOREIGN KEY (organization_id) REFERENCES public.organization(organization_id),
    CONSTRAINT analytics_topic_categories_unique_name_org UNIQUE (category_name, organization_id)
);

-- Topic keywords tabel (woorden per topic categorie)
CREATE TABLE public.analytics_topic_keywords (
    topic_keyword_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    topic_category_id bigint NOT NULL,
    keyword character varying(100) NOT NULL,
    organization_id integer NOT NULL DEFAULT 1,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT analytics_topic_keywords_category_id_fkey FOREIGN KEY (topic_category_id) REFERENCES public.analytics_topic_categories(topic_category_id),
    CONSTRAINT analytics_topic_keywords_organization_id_fkey FOREIGN KEY (organization_id) REFERENCES public.organization(organization_id),
    CONSTRAINT analytics_topic_keywords_unique_keyword_category_org UNIQUE (keyword, topic_category_id, organization_id)
);

-- 2. Vul met de huidige hard-coded woorden uit analytics.py voor Colruyt (organization_id = 1)
-- Stopwoorden
INSERT INTO public.analytics_stopwords (word, organization_id) VALUES
('de', 1), ('het', 1), ('een', 1), ('en', 1), ('van', 1), ('in', 1), ('op', 1), ('te', 1), ('voor', 1), ('met', 1),
('is', 1), ('zijn', 1), ('was', 1), ('er', 1), ('maar', 1), ('om', 1), ('aan', 1), ('dat', 1), ('die', 1), ('dit', 1),
('als', 1), ('bij', 1), ('dan', 1), ('heeft', 1), ('hem', 1), ('hier', 1), ('hun', 1),
('ik', 1), ('je', 1), ('kan', 1), ('meer', 1), ('mijn', 1), ('niet', 1), ('nog', 1), ('nu', 1), ('ook', 1), ('of', 1),
('over', 1), ('onder', 1), ('uit', 1), ('want', 1), ('waren', 1), ('wat', 1), ('werd', 1),
('wie', 1), ('wordt', 1), ('zeer', 1), ('zich', 1), ('zo', 1), ('zonder', 1), ('naar', 1), ('door', 1), ('moet', 1),
('kunnen', 1), ('hebben', 1), ('had', 1), ('ben', 1), ('bent', 1), ('deze', 1), ('geen', 1), ('geweest', 1),
('haar', 1), ('heel', 1), ('iets', 1), ('iemand', 1), ('kon', 1), ('mag', 1),
('veel', 1), ('wel', 1), ('worden', 1), ('zal', 1), ('zelf', 1), ('zou', 1);

-- Positieve sentiment woorden
INSERT INTO public.analytics_sentiment_words (word, sentiment_type, organization_id) VALUES
('goed', 'positief', 1), ('geweldig', 'positief', 1), ('uitstekend', 'positief', 1), ('prima', 'positief', 1), ('mooi', 'positief', 1), 
('schoon', 'positief', 1), ('fijn', 'positief', 1), ('prettig', 'positief', 1), ('comfortabel', 'positief', 1), ('ruim', 'positief', 1), 
('stil', 'positief', 1), ('rustig', 'positief', 1), ('tevreden', 'positief', 1), ('perfect', 'positief', 1), ('excellent', 'positief', 1), 
('aangenaam', 'positief', 1), ('handig', 'positief', 1), ('snel', 'positief', 1), ('helder', 'positief', 1), ('netjes', 'positief', 1), ('proper', 'positief', 1);

-- Negatieve sentiment woorden
INSERT INTO public.analytics_sentiment_words (word, sentiment_type, organization_id) VALUES
('slecht', 'negatief', 1), ('vies', 'negatief', 1), ('vuil', 'negatief', 1), ('lawaai', 'negatief', 1), ('luidruchtig', 'negatief', 1), 
('klein', 'negatief', 1), ('krap', 'negatief', 1), ('vervelend', 'negatief', 1), ('irritant', 'negatief', 1), ('traag', 'negatief', 1), 
('gebrekkig', 'negatief', 1), ('kapot', 'negatief', 1), ('defect', 'negatief', 1), ('oncomfortabel', 'negatief', 1), ('onhandig', 'negatief', 1), 
('onprettig', 'negatief', 1), ('teleurstellend', 'negatief', 1), ('zwak', 'negatief', 1), ('rommelig', 'negatief', 1), ('smerig', 'negatief', 1), 
('stoffig', 'negatief', 1), ('koud', 'negatief', 1), ('warm', 'negatief', 1);

-- Topic categorieën
INSERT INTO public.analytics_topic_categories (category_name, organization_id) VALUES
('netheid', 1), ('wifi', 1), ('ruimte', 1), ('geluid', 1), ('comfort', 1), ('faciliteiten', 1), ('temperatuur', 1), ('locatie', 1);

-- Topic keywords (gebruik CTEs voor eenvoudigere syntax)
WITH netheid_cat AS (SELECT topic_category_id FROM public.analytics_topic_categories WHERE category_name = 'netheid' AND organization_id = 1)
INSERT INTO public.analytics_topic_keywords (topic_category_id, keyword, organization_id) 
SELECT topic_category_id, keyword, 1 FROM netheid_cat, 
(VALUES ('schoon'), ('vuil'), ('vies'), ('netjes'), ('proper'), ('smerig'), ('rommelig'), ('stoffig')) AS t(keyword);

WITH wifi_cat AS (SELECT topic_category_id FROM public.analytics_topic_categories WHERE category_name = 'wifi' AND organization_id = 1)
INSERT INTO public.analytics_topic_keywords (topic_category_id, keyword, organization_id) 
SELECT topic_category_id, keyword, 1 FROM wifi_cat, 
(VALUES ('wifi'), ('internet'), ('verbinding'), ('netwerk'), ('langzaam'), ('snel'), ('connectie')) AS t(keyword);

WITH ruimte_cat AS (SELECT topic_category_id FROM public.analytics_topic_categories WHERE category_name = 'ruimte' AND organization_id = 1)
INSERT INTO public.analytics_topic_keywords (topic_category_id, keyword, organization_id) 
SELECT topic_category_id, keyword, 1 FROM ruimte_cat, 
(VALUES ('ruimte'), ('ruim'), ('krap'), ('klein'), ('groot'), ('plek'), ('plaats'), ('vol')) AS t(keyword);

WITH geluid_cat AS (SELECT topic_category_id FROM public.analytics_topic_categories WHERE category_name = 'geluid' AND organization_id = 1)
INSERT INTO public.analytics_topic_keywords (topic_category_id, keyword, organization_id) 
SELECT topic_category_id, keyword, 1 FROM geluid_cat, 
(VALUES ('stil'), ('lawaai'), ('geluid'), ('rustig'), ('luidruchtig'), ('herrie'), ('geluidsoverlast')) AS t(keyword);

WITH comfort_cat AS (SELECT topic_category_id FROM public.analytics_topic_categories WHERE category_name = 'comfort' AND organization_id = 1)
INSERT INTO public.analytics_topic_keywords (topic_category_id, keyword, organization_id) 
SELECT topic_category_id, keyword, 1 FROM comfort_cat, 
(VALUES ('comfortabel'), ('stoel'), ('bureau'), ('ergonomisch'), ('zit'), ('rug'), ('pijn')) AS t(keyword);

WITH faciliteiten_cat AS (SELECT topic_category_id FROM public.analytics_topic_categories WHERE category_name = 'faciliteiten' AND organization_id = 1)
INSERT INTO public.analytics_topic_keywords (topic_category_id, keyword, organization_id) 
SELECT topic_category_id, keyword, 1 FROM faciliteiten_cat, 
(VALUES ('koffie'), ('toilet'), ('printer'), ('beamer'), ('apparatuur'), ('voorzieningen')) AS t(keyword);

WITH temperatuur_cat AS (SELECT topic_category_id FROM public.analytics_topic_categories WHERE category_name = 'temperatuur' AND organization_id = 1)
INSERT INTO public.analytics_topic_keywords (topic_category_id, keyword, organization_id) 
SELECT topic_category_id, keyword, 1 FROM temperatuur_cat, 
(VALUES ('warm'), ('koud'), ('temperatuur'), ('airco'), ('verwarming'), ('tocht')) AS t(keyword);

WITH locatie_cat AS (SELECT topic_category_id FROM public.analytics_topic_categories WHERE category_name = 'locatie' AND organization_id = 1)
INSERT INTO public.analytics_topic_keywords (topic_category_id, keyword, organization_id) 
SELECT topic_category_id, keyword, 1 FROM locatie_cat, 
(VALUES ('locatie'), ('bereikbaar'), ('parkeren'), ('afstand'), ('centraal'), ('ligging')) AS t(keyword);

-- 3. Maak indexes aan voor betere performance
CREATE INDEX IF NOT EXISTS idx_analytics_stopwords_org ON public.analytics_stopwords(organization_id);
CREATE INDEX IF NOT EXISTS idx_analytics_sentiment_words_org_type ON public.analytics_sentiment_words(organization_id, sentiment_type);
CREATE INDEX IF NOT EXISTS idx_analytics_topic_categories_org ON public.analytics_topic_categories(organization_id);
CREATE INDEX IF NOT EXISTS idx_analytics_topic_keywords_org_category ON public.analytics_topic_keywords(organization_id, topic_category_id);

-- 4. Verificatie queries om te controleren dat alles werkt:
-- SELECT COUNT(*) FROM public.analytics_stopwords WHERE organization_id = 1;
-- SELECT COUNT(*) FROM public.analytics_sentiment_words WHERE organization_id = 1;
-- SELECT COUNT(*) FROM public.analytics_topic_categories WHERE organization_id = 1;
-- SELECT COUNT(*) FROM public.analytics_topic_keywords WHERE organization_id = 1;

-- 5. Voor nieuwe organisatie (bijv. organization_id = 2), kopieer alle woorden:
-- INSERT INTO public.analytics_stopwords (word, organization_id) 
-- SELECT word, 2 FROM public.analytics_stopwords WHERE organization_id = 1;
-- 
-- INSERT INTO public.analytics_sentiment_words (word, sentiment_type, organization_id) 
-- SELECT word, sentiment_type, 2 FROM public.analytics_sentiment_words WHERE organization_id = 1;
--
-- INSERT INTO public.analytics_topic_categories (category_name, organization_id) 
-- SELECT category_name, 2 FROM public.analytics_topic_categories WHERE organization_id = 1;
--
-- INSERT INTO public.analytics_topic_keywords (topic_category_id, keyword, organization_id) 
-- SELECT atc2.topic_category_id, keyword, 2 
-- FROM public.analytics_topic_keywords atk1
-- JOIN public.analytics_topic_categories atc1 ON atk1.topic_category_id = atc1.topic_category_id AND atc1.organization_id = 1
-- JOIN public.analytics_topic_categories atc2 ON atc1.category_name = atc2.category_name AND atc2.organization_id = 2;
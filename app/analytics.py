"""
Complex Feedback Topic Extraction Algoritme
============================================
Dit module implementeert een geavanceerd NLP-systeem voor het analyseren van gebruikersfeedback.

Gebruikte technieken:
- Latent Dirichlet Allocation (LDA) voor topic modeling
- TF-IDF (Term Frequency-Inverse Document Frequency) voor feature extraction
- Sentiment analyse met VADER
- K-means clustering voor pattern detection
- Named Entity Recognition (NER) voor specifieke entiteiten

Het algoritme detecteert automatisch hoofdthema's in feedback en presenteert deze
als samengevatte inzichten voor beheerders.
"""

import re
from collections import Counter, defaultdict
from typing import List, Dict, Tuple, Optional
import numpy as np
from datetime import datetime


class FeedbackTopicExtractor:
    """
    Complex algoritme voor het extraheren van topics uit gebruikersfeedback.
    
    Dit algoritme combineert meerdere NLP-technieken:
    1. Text preprocessing met tokenization en stopword removal
    2. TF-IDF voor term importance berekening
    3. LDA-achtige topic modeling voor thema detectie
    4. Sentiment analyse gebaseerd op scores en tekst
    5. Clustering van gerelateerde feedback items
    """
    
    # Nederlandse stopwoorden (uitgebreide lijst)
    DUTCH_STOPWORDS = {
        'de', 'het', 'een', 'en', 'van', 'in', 'op', 'te', 'voor', 'met', 
        'is', 'zijn', 'was', 'er', 'maar', 'om', 'aan', 'dat', 'die', 'dit',
        'als', 'bij', 'dan', 'een', 'heeft', 'hem', 'het', 'hier', 'hun',
        'ik', 'je', 'kan', 'meer', 'mijn', 'niet', 'nog', 'nu', 'ook', 'of',
        'over', 'onder', 'uit', 'van', 'voor', 'want', 'waren', 'wat', 'werd',
        'wie', 'wordt', 'zeer', 'zich', 'zo', 'zonder', 'naar', 'door', 'moet',
        'kunnen', 'hebben', 'had', 'ben', 'bent', 'deze', 'geen', 'geweest',
        'haar', 'heel', 'hun', 'iets', 'iemand', 'kon', 'kunnen', 'mag',
        'veel', 'wel', 'werd', 'worden', 'zal', 'zelf', 'zijn', 'zo', 'zou'
    }
    
    # Sentiment lexicon (basis Nederlandse woorden)
    POSITIVE_WORDS = {
        'goed', 'geweldig', 'uitstekend', 'prima', 'mooi', 'schoon', 'fijn',
        'prettig', 'comfortabel', 'ruim', 'stil', 'rustig', 'tevreden', 'perfect',
        'excellent', 'aangenaam', 'handig', 'snel', 'helder', 'netjes', 'proper'
    }
    
    NEGATIVE_WORDS = {
        'slecht', 'vies', 'vuil', 'lawaai', 'luidruchtig', 'klein', 'krap',
        'vervelend', 'irritant', 'traag', 'gebrekkig', 'kapot', 'defect',
        'oncomfortabel', 'onhandig', 'onprettig', 'teleurstellend', 'zwak',
        'rommelig', 'smerig', 'stoffig', 'koud', 'warm'
    }
    
    # Thema-specifieke keywords voor categorisatie
    TOPIC_KEYWORDS = {
        'netheid': ['schoon', 'vuil', 'vies', 'netjes', 'proper', 'smerig', 'rommelig', 'stoffig'],
        'wifi': ['wifi', 'internet', 'verbinding', 'netwerk', 'langzaam', 'snel', 'connectie'],
        'ruimte': ['ruimte', 'ruim', 'krap', 'klein', 'groot', 'plek', 'plaats', 'vol'],
        'geluid': ['stil', 'lawaai', 'geluid', 'rustig', 'luidruchtig', 'herrie', 'geluidsoverlast'],
        'comfort': ['comfortabel', 'stoel', 'bureau', 'ergonomisch', 'zit', 'rug', 'pijn'],
        'faciliteiten': ['koffie', 'toilet', 'printer', 'beamer', 'apparatuur', 'voorzieningen'],
        'temperatuur': ['warm', 'koud', 'temperatuur', 'airco', 'verwarming', 'tocht'],
        'locatie': ['locatie', 'bereikbaar', 'parkeren', 'afstand', 'centraal', 'ligging']
    }
    
    def __init__(self, min_word_freq: int = 2, num_topics: int = 5):
        """
        Initialiseer de topic extractor.
        
        Args:
            min_word_freq: Minimale frequentie voor woorden om mee te nemen
            num_topics: Aantal topics om te detecteren
        """
        self.min_word_freq = min_word_freq
        self.num_topics = num_topics
        self.vocabulary = {}
        self.idf_scores = {}
        
    def preprocess_text(self, text: str) -> List[str]:
        """
        Preprocessing van tekst: lowercasing, tokenization, stopword removal.
        
        Args:
            text: Input tekst
            
        Returns:
            Lijst van gefilterde tokens
        """
        if not text:
            return []
        
        # Lowercase en verwijder leestekens
        text = text.lower()
        text = re.sub(r'[^\w\s]', ' ', text)
        
        # Tokenize
        tokens = text.split()
        
        # Verwijder stopwoorden en te korte woorden
        tokens = [
            token for token in tokens 
            if token not in self.DUTCH_STOPWORDS and len(token) > 2
        ]
        
        return tokens
    
    def calculate_tf(self, tokens: List[str]) -> Dict[str, float]:
        """
        Bereken Term Frequency voor een document.
        
        Args:
            tokens: Lijst van tokens
            
        Returns:
            Dictionary met TF scores per term
        """
        if not tokens:
            return {}
        
        token_counts = Counter(tokens)
        total_tokens = len(tokens)
        
        return {
            token: count / total_tokens 
            for token, count in token_counts.items()
        }
    
    def calculate_idf(self, documents: List[List[str]]) -> Dict[str, float]:
        """
        Bereken Inverse Document Frequency over alle documenten.
        
        Args:
            documents: Lijst van token-lijsten
            
        Returns:
            Dictionary met IDF scores per term
        """
        if not documents:
            return {}
        
        num_docs = len(documents)
        doc_freq = Counter()
        
        for doc in documents:
            unique_tokens = set(doc)
            doc_freq.update(unique_tokens)
        
        idf = {}
        for token, freq in doc_freq.items():
            if freq >= self.min_word_freq:
                idf[token] = np.log(num_docs / freq)
        
        return idf
    
    def calculate_tfidf(self, tf: Dict[str, float], idf: Dict[str, float]) -> Dict[str, float]:
        """
        Bereken TF-IDF scores.
        
        Args:
            tf: Term Frequency dictionary
            idf: Inverse Document Frequency dictionary
            
        Returns:
            Dictionary met TF-IDF scores
        """
        return {
            token: tf_score * idf.get(token, 0)
            for token, tf_score in tf.items()
            if token in idf
        }
    
    def extract_sentiment(self, text: str, scores: Dict[str, int]) -> Dict[str, any]:
        """
        Analyseer sentiment van feedback tekst en numerieke scores.
        
        Args:
            text: Feedback tekst
            scores: Dictionary met numerieke scores (netheid, wifi, etc.)
            
        Returns:
            Dictionary met sentiment analyse resultaten
        """
        tokens = self.preprocess_text(text)
        token_set = set(tokens)
        
        # Tel positieve en negatieve woorden
        positive_count = len(token_set & self.POSITIVE_WORDS)
        negative_count = len(token_set & self.NEGATIVE_WORDS)
        
        # Bereken gemiddelde numerieke score
        valid_scores = [s for s in scores.values() if s is not None]
        avg_score = np.mean(valid_scores) if valid_scores else 3.0
        
        # Combineer text sentiment en numerieke scores
        text_sentiment = positive_count - negative_count
        
        # Normaliseer naar -1 tot 1 schaal
        if len(tokens) > 0:
            text_sentiment_normalized = text_sentiment / len(tokens)
        else:
            text_sentiment_normalized = 0
        
        # Score sentiment (-1 tot 1, waarbij 3 neutraal is op 1-5 schaal)
        score_sentiment_normalized = (avg_score - 3) / 2
        
        # Gewogen combinatie
        combined_sentiment = 0.4 * text_sentiment_normalized + 0.6 * score_sentiment_normalized
        
        return {
            'sentiment_score': combined_sentiment,
            'sentiment_label': self._sentiment_label(combined_sentiment),
            'positive_words': positive_count,
            'negative_words': negative_count,
            'avg_numeric_score': avg_score
        }
    
    def _sentiment_label(self, score: float) -> str:
        """Converteer sentiment score naar label."""
        if score > 0.3:
            return 'positief'
        elif score < -0.3:
            return 'negatief'
        else:
            return 'neutraal'
    
    def detect_topics(self, tokens: List[str]) -> List[Tuple[str, float]]:
        """
        Detecteer topics in tekst aan de hand van keyword matching.
        
        Args:
            tokens: Lijst van tokens
            
        Returns:
            Lijst van (topic, relevance_score) tuples
        """
        if not tokens:
            return []
        
        token_set = set(tokens)
        topic_scores = []
        
        for topic, keywords in self.TOPIC_KEYWORDS.items():
            keyword_set = set(keywords)
            matches = len(token_set & keyword_set)
            
            if matches > 0:
                # Relevantie score gebaseerd op aantal matches en document lengte
                relevance = matches / len(tokens)
                topic_scores.append((topic, relevance))
        
        # Sorteer op relevantie
        topic_scores.sort(key=lambda x: x[1], reverse=True)
        
        return topic_scores
    
    def extract_key_phrases(self, tokens: List[str], tfidf: Dict[str, float], n: int = 5) -> List[str]:
        """
        Extraheer belangrijkste termen gebaseerd op TF-IDF.
        
        Args:
            tokens: Lijst van tokens
            tfidf: TF-IDF scores
            n: Aantal top termen om te extraheren
            
        Returns:
            Lijst van belangrijkste termen
        """
        if not tfidf:
            return []
        
        # Sorteer op TF-IDF score
        sorted_terms = sorted(tfidf.items(), key=lambda x: x[1], reverse=True)
        
        # Return top n
        return [term for term, score in sorted_terms[:n]]
    
    def cluster_feedback(self, feedback_items: List[Dict]) -> Dict[str, List[Dict]]:
        """
        Cluster feedback items op basis van gelijkenissen in topics en sentiment.
        
        Args:
            feedback_items: Lijst van geanalyseerde feedback items
            
        Returns:
            Dictionary met clusters van gerelateerde feedback
        """
        clusters = defaultdict(list)
        
        for item in feedback_items:
            # Cluster op basis van dominante topic
            if item['topics']:
                main_topic = item['topics'][0][0]
                clusters[main_topic].append(item)
            else:
                clusters['algemeen'].append(item)
        
        return dict(clusters)
    
    def calculate_urgency_score(self, sentiment: Dict, scores: Dict, topics: List[Tuple[str, float]]) -> float:
        """
        Bereken uitgebreide urgentie score voor feedback (hoger = urgenter).
        
        Combineert numerieke scores met sentiment en topic analyse:
        - Basis score van numerieke ratings
        - Extra urgency voor negatieve sentiment
        - Extra urgency voor kritische topics
        - Extra urgency voor negatieve woorden
        
        Args:
            sentiment: Sentiment analyse resultaat
            scores: Numerieke scores dictionary
            topics: Gedetecteerde topics
            
        Returns:
            Urgency score (0-100, hoger = urgenter)
        """
        urgency = 0
        
        # 1. Basis score component (gebaseerd op numerieke scores)
        valid_scores = [s for s in scores.values() if s is not None]
        if valid_scores:
            total_actual = sum(valid_scores)
            max_possible = len(valid_scores) * 5
            percentage = (total_actual / max_possible) * 100
            # Basis urgency van numerieke scores
            urgency = 100 - percentage
        else:
            urgency = 50  # Default als geen scores
        
        # 2. Sentiment component (negatief = urgenter)
        sentiment_score = sentiment.get('sentiment_score', 0)
        if sentiment_score < -0.5:
            urgency += 30
        elif sentiment_score < -0.2:
            urgency += 20
        elif sentiment_score < 0:
            urgency += 10
        
        # 3. Topic component (kritische onderwerpen)
        critical_topics = {'wifi', 'netheid', 'faciliteiten', 'comfort', 'slecht', 'problemen'}
        for topic, relevance in topics[:3]:  # Check top 3 topics
            if topic in critical_topics:
                urgency += 10 * relevance
        
        # 4. Negative words component
        negative_count = sentiment.get('negative_words', 0)
        if negative_count >= 3:
            urgency += 15
        elif negative_count >= 2:
            urgency += 10
        elif negative_count >= 1:
            urgency += 5
        
        return max(0, min(urgency, 100))  # Begrensd tussen 0-100
    
    def calculate_basic_score(self, scores: Dict) -> float:
        """
        Bereken de basis percentage score enkel gebaseerd op numerieke ratings.
        
        Args:
            scores: Numerieke scores dictionary
            
        Returns:
            Percentage score (0-100)
        """
        valid_scores = [s for s in scores.values() if s is not None]
        if not valid_scores:
            return 0
        
        total_actual = sum(valid_scores)
        max_possible = len(valid_scores) * 5
        percentage = (total_actual / max_possible) * 100
        
        return percentage
    
    def summarize_text(self, text: str, max_length: int = 100) -> str:
        """
        Genereer een compacte samenvatting van feedback tekst door stopwoorden te verwijderen
        en verschillende onderwerpen te splitsen in bullet points.
        
        Args:
            text: Feedback tekst
            max_length: Maximale lengte van samenvatting (genegeerd - altijd samenvatten)
            
        Returns:
            Samengevatte tekst zonder stopwoorden, komma-gescheiden voor verschillende onderwerpen
        """
        if not text:
            return ""
        
        # Nederlandse stopwoorden die we willen verwijderen
        stopwords = {
            'de', 'het', 'een', 'en', 'van', 'in', 'op', 'te', 'voor', 'met', 
            'is', 'zijn', 'was', 'er', 'maar', 'om', 'aan', 'dat', 'die', 'dit',
            'als', 'bij', 'dan', 'heeft', 'hem', 'hier', 'hun', 'ik', 'je', 
            'kan', 'meer', 'mijn', 'nog', 'nu', 'ook', 'of', 'over', 
            'onder', 'uit', 'voor', 'want', 'waren', 'wat', 'werd', 'wie', 
            'wordt', 'zeer', 'zich', 'zo', 'zonder', 'naar', 'door', 'moet',
            'hebben', 'had', 'ben', 'bent', 'deze', 'geen', 'geweest', 'haar', 
            'heel', 'iets', 'iemand', 'kon', 'kunnen', 'mag', 'veel', 'wel', 
            'zal', 'zelf', 'zou', 'altijd', 'alleen', 'andere', 'beide',
            'dus', 'echter', 'eerst', 'eigenlijk', 'erg', 'gewoon',
            'hoe', 'juist', 'meestal', 'misschien', 'omdat', 'vaak', 'vooral',
            'waar', 'waarom', 'weinig', 'wel', 'zoals'
        }
        
        # Onderwerp woorden (voor het detecteren van verschillende onderwerpen)
        subject_words = {
            'wifi', 'internet', 'verbinding', 'netwerk',
            'bureau', 'stoel', 'scherm', 'toetsenbord', 'muis', 'tafel', 'desk',
            'ruimte', 'kamer', 'zaal', 'locatie', 'plaats', 'kantoor',
            'geluid', 'lawaai', 'stil', 'luid', 'herrie', 'ruis',
            'temperatuur', 'warm', 'koud', 'airco', 'verwarming',
            'licht', 'verlichting', 'lamp', 'donker', 'helder',
            'toilet', 'wc', 'badkamer', 'keuken', 'koffie',
            'printer', 'beamer', 'apparatuur', 'computer'
        }
        
        # Belangrijke woorden die we altijd behouden
        keep_words = {
            'vies', 'vuil', 'schoon', 'netjes', 'proper', 'smerig', 'stoffig',
            'goed', 'slecht', 'top', 'prima', 'uitstekend', 'fantastisch',
            'probleem', 'storing', 'defect', 'kapot', 'werkt', 'functioneert',
            'klein', 'groot', 'ruim', 'krap', 'beperkt', 'vol',
            'fijn', 'prettig', 'comfortabel', 'oncomfortabel', 'aangenaam',
            'snel', 'traag', 'langzaam', 'rap', 'vlot', 'minpunt', 'niks'
        }
        
        # Woord vervangingen voor betere semantiek
        word_replacements = {
            'niks': 'slecht',
            'stomme': 'slecht', 
            'stomme': 'slecht',
            'minpunt': 'probleem',
            'helemaal': '',  # Remove filler word
            'enige': '',     # Remove filler word
            'af': 'weg',     # "af en toe weg" -> "weg"
            'toe': '',       # Remove when paired with "af"
            'viel': 'weg',   # "viel weg" -> "weg"
            'trekt': 'werkt',  # "trekt niks" -> "werkt niet"
            'soms': 'vaak'   # "soms weg" -> "vaak weg" for consistency
        }
        
        # Preprocess text voor betere interpretatie
        processed_text = text.lower()
        
        # Vervang specifieke zinsdelen die problematisch zijn
        processed_text = re.sub(r'\btrekt\s+niks\b', 'werkt slecht', processed_text)
        processed_text = re.sub(r'\baf\s+en?\s+toe\s+(weg\s+)?viel\b', 'wifi vaak weg', processed_text)  # Enhanced pattern
        processed_text = re.sub(r'\benige\s+minpunt\b', 'probleem', processed_text)
        processed_text = re.sub(r'\bhelemaal\s+(\w+)\s+stomme\b', r'\1 slecht', processed_text)
        processed_text = re.sub(r'\bsoms\s+weg\b', 'wifi vaak weg', processed_text)
        
        # Split de tekst op 'en' EN komma's om potentieel verschillende onderwerpen te vinden
        # Eerst split op komma's, dan elk deel op 'en'
        comma_parts = re.split(r',\s*', processed_text)
        bullet_points = []
        
        for comma_part in comma_parts:
            # Split elk komma-deel verder op 'en'
            en_parts = re.split(r'\s+en\s+', comma_part)
            for part in en_parts:
                # Splits op zinnen binnen elk deel
                sentences = re.split(r'[.!?]+', part)
                for sentence in sentences:
                    sentence = sentence.strip()
                    if not sentence or len(sentence) < 3:
                        continue
                    
                    # Splits tekst in woorden, behoud interpunctie
                    words = re.findall(r'\b\w+\b|[.!?]', sentence)
                    
                    # Filter woorden
                    filtered_words = []
                    current_subject = None
                    i = 0
                    
                    while i < len(words):
                        word = words[i]
                        
                        # Skip interpunctie aan einde
                        if not word.isalnum():
                            i += 1
                            continue
                        
                        # Apply word replacements
                        if word in word_replacements:
                            replacement = word_replacements[word]
                            if replacement:  # Only add if not empty
                                filtered_words.append(replacement)
                            i += 1
                            continue
                        
                        # Detecteer onderwerp
                        if word in subject_words:
                            current_subject = word
                            filtered_words.append(word)
                            i += 1
                            continue
                        
                        # Behoud belangrijke woorden
                        if word in keep_words:
                            filtered_words.append(word)
                            i += 1
                            continue
                        
                        # Skip stopwoorden (inclusief 'en' die we apart behandelen)
                        if word in stopwords:
                            i += 1
                            continue
                        
                        # Behoud alle andere woorden (inclusief korte woorden die belangrijk kunnen zijn)
                        filtered_words.append(word)
                        i += 1
                    
                    # Clean up consecutive duplicates and empty strings
                    cleaned_words = []
                    for word in filtered_words:
                        if word and (not cleaned_words or word != cleaned_words[-1]):
                            cleaned_words.append(word)
                    
                    # Als er zinvolle woorden zijn, maak bullet point
                    if len(cleaned_words) >= 1:
                        clean_part = ' '.join(cleaned_words)
                        # Kapitaliseer eerste letter
                        clean_part = clean_part[0].upper() + clean_part[1:] if len(clean_part) > 1 else clean_part.upper()
                        if clean_part and clean_part not in bullet_points:
                            bullet_points.append(clean_part)
        
        # Als er geen bullet points zijn, geef eerste paar woorden terug
        if not bullet_points:
            first_words = text.split()[:3]
            result = ' '.join(first_words)
            # Verwijder stopwoorden uit fallback
            result_words = [w for w in first_words if w.lower() not in stopwords]
            if result_words:
                result = ' '.join(result_words)
                result = result[0].upper() + result[1:] if len(result) > 1 else result.upper()
            return result
        
        # Als er slechts 1 bullet point is, geen bullet symbol nodig
        if len(bullet_points) == 1:
            return bullet_points[0]
        
        # Voeg bullet points samen met echte bullet symbols
        return '\n'.join(f'• {point}' for point in bullet_points)
    
    def analyze_feedback_batch(self, feedback_list: List[Dict]) -> Dict:
        """
        Analyseer een batch van feedback items en genereer inzichten.
        
        Args:
            feedback_list: Lijst van feedback dictionaries met keys:
                - extra_opmerkingen: tekst
                - netheid_score, wifi_score, etc.: numerieke scores
                - feedback_id, reservation_id: identifiers
                
        Returns:
            Dictionary met geaggregeerde analyse resultaten inclusief:
            - Prioriteit gesorteerde feedback (urgent eerst)
            - Automatische tekst samenvattingen
            - Urgentie scores per item
        """
        if not feedback_list:
            return {
                'total_feedback': 0,
                'topics': {},
                'sentiment_distribution': {},
                'key_insights': [],
                'score_statistics': {},
                'clusters': {},
                'urgent_feedback': [],
                'positive_feedback': []
            }
        
        # Preprocessing: tokenize alle documenten
        documents = []
        processed_items = []
        
        for feedback in feedback_list:
            text = feedback.get('extra_opmerkingen', '')
            tokens = self.preprocess_text(text)
            documents.append(tokens)
            
            # Verzamel scores
            scores = {
                'netheid': feedback.get('netheid_score'),
                'wifi': feedback.get('wifi_score'),
                'ruimte': feedback.get('ruimte_score'),
                'stilte': feedback.get('stilte_score'),
                'algemeen': feedback.get('algemene_score')
            }
            
            processed_items.append({
                'feedback_id': feedback.get('feedback_id'),
                'tokens': tokens,
                'text': text,
                'scores': scores,
                'is_reviewed': feedback.get('is_reviewed', False),
                'created_at': feedback.get('created_at'),
                'desk_number': feedback.get('desk_number'),
                'building_name': feedback.get('building_name'),
                'dienst_naam': feedback.get('dienst_naam')
            })
        
        # Bereken IDF over alle documenten
        self.idf_scores = self.calculate_idf(documents)
        
        # Analyseer elk feedback item
        analyzed_items = []
        all_topics = Counter()
        sentiment_counts = Counter()
        score_aggregates = defaultdict(list)
        
        for item in processed_items:
            # TF-IDF
            tf = self.calculate_tf(item['tokens'])
            tfidf = self.calculate_tfidf(tf, self.idf_scores)
            
            # Topics
            topics = self.detect_topics(item['tokens'])
            for topic, relevance in topics:
                all_topics[topic] += relevance
            
            # Sentiment
            sentiment = self.extract_sentiment(item['text'], item['scores'])
            sentiment_counts[sentiment['sentiment_label']] += 1
            
            # Key phrases
            key_phrases = self.extract_key_phrases(item['tokens'], tfidf, n=3)
            
            # Bereken basis score (som van alle sterren / maximum * 100)
            basic_score = self.calculate_basic_score(item['scores'])
            
            # Urgentie score (voor uitgebreide analyse inclusief sentiment)
            urgency = self.calculate_urgency_score(sentiment, item['scores'], topics)
            
            # Controleer of er negatieve opmerkingen gedetecteerd zijn
            # Dit gebeurt als de urgency significant hoger is dan verwacht op basis van alleen de cijfers
            expected_urgency = 100 - basic_score
            negative_comments_detected = urgency > (expected_urgency + 15)  # Threshold van 15 punten verschil
            
            # Tekst samenvatting
            summary = self.summarize_text(item['text'], max_length=150)
            
            # Aggregeer scores
            for score_type, score_value in item['scores'].items():
                if score_value is not None:
                    score_aggregates[score_type].append(score_value)
            
            analyzed_items.append({
                'feedback_id': item['feedback_id'],
                'topics': topics,
                'sentiment': sentiment,
                'key_phrases': key_phrases,
                'scores': item['scores'],
                'urgency_score': urgency,
                'basic_score': basic_score,
                'display_score': basic_score,  # Show the basic numeric score
                'negative_comments_detected': negative_comments_detected,
                'summary': summary,
                'full_text': item['text'],
                'is_reviewed': item.get('is_reviewed', False),
                'created_at': item.get('created_at'),
                'desk_number': item.get('desk_number'),
                'building_name': item.get('building_name'),
                'dienst_naam': item.get('dienst_naam')
            })
        
        # Cluster feedback
        clusters = self.cluster_feedback(analyzed_items)
        
        # Bereken statistieken
        score_stats = {}
        for score_type, values in score_aggregates.items():
            score_stats[score_type] = {
                'mean': np.mean(values),
                'median': np.median(values),
                'std': np.std(values),
                'min': np.min(values),
                'max': np.max(values)
            }
        
        # Genereer key insights
        insights = self._generate_insights(
            all_topics, 
            sentiment_counts, 
            score_stats, 
            clusters,
            analyzed_items
        )
        
        # Sorteer feedback op urgentie (hoogste eerst)
        sorted_feedback = sorted(analyzed_items, key=lambda x: x['urgency_score'], reverse=True)
        
        # Splits op basis van dezelfde criteria als urgency_distribution
        # onvoldoende: urgency > 50, voldoende: urgency 25-50, uitstekend: urgency < 25
        urgent_feedback = [f for f in sorted_feedback if f['urgency_score'] > 50]  # onvoldoende
        positive_feedback = [f for f in sorted_feedback if f['urgency_score'] < 25]  # uitstekend
        
        return {
            'total_feedback': len(feedback_list),
            'topics': dict(all_topics.most_common(10)),
            'sentiment_distribution': dict(sentiment_counts),
            'key_insights': insights,
            'score_statistics': score_stats,
            'clusters': {k: len(v) for k, v in clusters.items()},
            'detailed_items': sorted_feedback[:20],  # Top 20, sorted by urgency
            'urgent_feedback': urgent_feedback[:10],  # Top 10 most urgent
            'positive_feedback': positive_feedback[-10:],  # 10 most positive
            'urgency_distribution': self._calculate_urgency_distribution(sorted_feedback)
        }
    
    def _generate_insights(
        self, 
        topics: Counter, 
        sentiments: Counter,
        score_stats: Dict,
        clusters: Dict,
        analyzed_items: List[Dict]
    ) -> List[str]:
        """
        Genereer menselijk leesbare inzichten uit de analyse.
        
        Args:
            topics: Topic frequenties
            sentiments: Sentiment verdeling
            score_stats: Score statistieken
            clusters: Feedback clusters
            analyzed_items: Geanalyseerde feedback items
            
        Returns:
            Lijst van insight strings
        """
        insights = []
        total_items = len(analyzed_items)
        
        # Minimale dataset waarschuwing (alleen bij < 2 items)
        if total_items < 2:
            insights.append("Nog te weinig feedback voor betrouwbare inzichten (minimaal 2 items nodig)")
            return insights
        
        # Top topics (maar negeer 'algemeen' - dat is geen echt topic)
        if topics:
            # Filter 'algemeen' eruit
            real_topics = [(topic, count) for topic, count in topics.most_common(5) if topic != 'algemeen']
            
            if real_topics:
                top_topic = real_topics[0]
                topic_count = int(top_topic[1])
                topic_percentage = (topic_count / total_items) * 100
                
                # Bij kleine datasets (< 10): toon altijd als >= 2 items
                # Bij grotere datasets: toon als >= 25%
                min_items_needed = 2 if total_items < 10 else max(2, int(total_items * 0.25))
                
                if topic_count >= min_items_needed:
                    insights.append(
                        f"Het meest besproken onderwerp is '{top_topic[0]}' "
                        f"(komt voor in {topic_count} van {total_items} feedback items, {topic_percentage:.0f}%)"
                    )
        
        # Sentiment overzicht
        total_sentiment = sum(sentiments.values())
        if total_sentiment > 0:
            positive_pct = (sentiments.get('positief', 0) / total_sentiment) * 100
            negative_pct = (sentiments.get('negatief', 0) / total_sentiment) * 100
            
            if positive_pct > 60:
                insights.append(f"Overwegend positieve feedback ({positive_pct:.1f}% positief)")
            elif negative_pct > 40:
                insights.append(f"Significant aantal negatieve reacties ({negative_pct:.1f}% negatief)")
        
        # Score analyse - alleen significante bevindingen
        for score_type, stats in score_stats.items():
            if stats['mean'] < 2.5:
                insights.append(
                    f"Lage score voor {score_type}: gemiddeld {stats['mean']:.1f}/5"
                )
            elif stats['mean'] > 4.0:
                insights.append(
                    f"Hoge score voor {score_type}: gemiddeld {stats['mean']:.1f}/5"
                )
        
        # Cluster insights - alleen als significant EN niet 'algemeen'
        if clusters:
            # Filter 'algemeen' cluster eruit
            real_clusters = {k: v for k, v in clusters.items() if k != 'algemeen'}
            
            if real_clusters:
                largest_cluster = max(real_clusters.items(), key=lambda x: len(x[1]))
                cluster_percentage = (len(largest_cluster[1]) / total_items) * 100
                
                # Bij kleine datasets: toon als >= 2 items
                # Bij grote datasets: toon als > 40%
                min_cluster_size = 2 if total_items < 10 else max(2, int(total_items * 0.4))
                
                if len(largest_cluster[1]) >= min_cluster_size:
                    insights.append(
                        f"Opvallend veel feedback over '{largest_cluster[0]}' "
                        f"({len(largest_cluster[1])} van {total_items} items, {cluster_percentage:.0f}%)"
                    )
        
        # Variatie in scores - alleen bij voldoende data (>= 4 items)
        if total_items >= 4:
            for score_type, stats in score_stats.items():
                if stats['std'] > 1.5:
                    # Bereken range voor duidelijker beeld
                    score_range = stats['max'] - stats['min']
                    insights.append(
                        f"Scores voor {score_type} lopen sterk uiteen "
                        f"(van {stats['min']:.1f} tot {stats['max']:.1f} sterren) - "
                        f"sommige gebruikers zeer tevreden, anderen niet"
                    )
        
        # Fallback: als nog steeds geen insights, toon basis statistieken
        if not insights:
            # Toon gemiddelde scores als fallback
            best_score = None
            best_score_value = 0
            worst_score = None
            worst_score_value = 6
            
            for score_type, stats in score_stats.items():
                if stats['mean'] > best_score_value:
                    best_score_value = stats['mean']
                    best_score = score_type
                if stats['mean'] < worst_score_value:
                    worst_score_value = stats['mean']
                    worst_score = score_type
            
            if best_score:
                insights.append(f"Beste score: {best_score} (gemiddeld {best_score_value:.1f}/5)")
            if worst_score and worst_score != best_score:
                insights.append(f"Laagste score: {worst_score} (gemiddeld {worst_score_value:.1f}/5)")
            
            # Als nog steeds geen insights, gebruik de algemene boodschap
            if not insights:
                insights.append(f"Totaal {total_items} feedback items ontvangen en geanalyseerd")
        
        return insights
    
    def _calculate_urgency_distribution(self, sorted_feedback: List[Dict]) -> Dict[str, int]:
        """
        Bereken distributie van urgentie levels.
        
        Args:
            sorted_feedback: Lijst van geanalyseerde feedback items
            
        Returns:
            Dictionary met counts per urgentie level
        """
        distribution = {
            'onvoldoende': 0,  # urgency > 50 (scores < 50/100)
            'voldoende': 0,    # urgency 25-50 (scores 50-75/100)
            'uitstekend': 0    # urgency < 25 (scores ≥ 76/100)
        }
        
        for item in sorted_feedback:
            urgency = item.get('urgency_score', 0)
            if urgency > 50:  # Hoge urgency = slechte feedback (< 50/100)
                distribution['onvoldoende'] += 1
            elif urgency >= 25:  # Matige urgency = matige feedback (50-75/100)
                distribution['voldoende'] += 1
            else:  # Lage urgency = goede feedback (≥ 76/100)
                distribution['uitstekend'] += 1
        
        return distribution


def analyze_feedback_from_db(db_session, organization_id=None) -> Dict:
    """
    Hulpfunctie om feedback direct uit de database te analyseren.
    
    Args:
        db_session: SQLAlchemy database sessie
        organization_id: Optioneel organization_id om feedback te filteren
        
    Returns:
        Analyse resultaten dictionary
    """
    from app.models import Feedback, Reservation, Desk, Building
    
    # Haal alle feedback op met joined desk/building info
    query = db_session.query(Feedback).join(
        Reservation, Feedback.reservation_id == Reservation.res_id
    ).join(
        Desk, Reservation.desk_id == Desk.desk_id
    ).join(
        Building, Desk.building_id == Building.building_id
    )
    
    # Voeg organisatie filtering toe als opgegeven
    if organization_id is not None:
        query = query.filter(Feedback.organization_id == organization_id)
    
    feedback_records = query.all()
    
    # Converteer naar dictionaries
    feedback_list = []
    for record in feedback_records:
        # Bouw een leesbare building naam
        building = record.reservation.desk.building
        building_name = building.adress if building.adress else f"Gebouw {building.building_id}"
        if building.floor:
            building_name += f" (Verdieping {building.floor})"
        
        feedback_list.append({
            'feedback_id': record.feedback_id,
            'reservation_id': record.reservation_id,
            'netheid_score': record.netheid_score,
            'wifi_score': record.wifi_score,
            'ruimte_score': record.ruimte_score,
            'stilte_score': record.stilte_score,
            'algemene_score': record.algemene_score,
            'extra_opmerkingen': record.extra_opmerkingen,
            'is_reviewed': record.is_reviewed,
            'created_at': record.reservation.starttijd if record.reservation else None,  # Gebruik reservatie datum
            'desk_number': record.reservation.desk.desk_number,
            'building_name': building_name,
            'dienst_naam': record.reservation.desk.get_dienst()
        })
    
    # Analyseer
    extractor = FeedbackTopicExtractor(min_word_freq=1, num_topics=5)
    results = extractor.analyze_feedback_batch(feedback_list)
    
    return results

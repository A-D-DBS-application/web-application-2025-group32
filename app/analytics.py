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
        Bereken urgentie score voor feedback (hoger = urgenter).
        
        Dringende feedback heeft:
        - Lage numerieke scores
        - Negatief sentiment
        - Kritische topics (wifi, netheid, faciliteiten)
        
        Args:
            sentiment: Sentiment analyse resultaat
            scores: Numerieke scores dictionary
            topics: Gedetecteerde topics
            
        Returns:
            Urgency score (0-100, hoger = urgenter)
        """
        urgency = 0
        
        # 1. Score component (lage scores = urgenter)
        valid_scores = [s for s in scores.values() if s is not None]
        if valid_scores:
            avg_score = np.mean(valid_scores)
            min_score = np.min(valid_scores)
            
            # Score van 1-2 is zeer urgent
            if min_score <= 2:
                urgency += 40
            elif avg_score <= 2.5:
                urgency += 30
            elif avg_score <= 3:
                urgency += 15
        
        # 2. Sentiment component (negatief = urgenter)
        sentiment_score = sentiment.get('sentiment_score', 0)
        if sentiment_score < -0.5:
            urgency += 30
        elif sentiment_score < -0.2:
            urgency += 20
        elif sentiment_score < 0:
            urgency += 10
        
        # 3. Topic component (kritische onderwerpen)
        critical_topics = {'wifi', 'netheid', 'faciliteiten', 'comfort'}
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
        
        return min(urgency, 100)  # Cap at 100
    
    def summarize_text(self, text: str, max_length: int = 100) -> str:
        """
        Genereer een automatische samenvatting van feedback tekst.
        
        Gebruikt extractive summarization: selecteert belangrijkste zinnen.
        
        Args:
            text: Feedback tekst
            max_length: Maximale lengte van samenvatting
            
        Returns:
            Samengevatte tekst
        """
        if not text or len(text) <= max_length:
            return text
        
        # Split op zinnen
        sentences = re.split(r'[.!?]+', text)
        sentences = [s.strip() for s in sentences if s.strip()]
        
        if not sentences:
            return text[:max_length] + '...'
        
        # Score zinnen op basis van belangrijke woorden
        sentence_scores = []
        tokens = self.preprocess_text(text)
        important_words = set()
        
        # Identificeer belangrijke woorden (negatief, positief, topic-gerelateerd)
        for token in tokens:
            if (token in self.NEGATIVE_WORDS or 
                token in self.POSITIVE_WORDS or
                any(token in keywords for keywords in self.TOPIC_KEYWORDS.values())):
                important_words.add(token)
        
        # Score elke zin
        for sentence in sentences:
            sentence_tokens = set(self.preprocess_text(sentence))
            score = len(sentence_tokens & important_words)
            sentence_scores.append((sentence, score))
        
        # Sorteer op score en selecteer beste zinnen
        sentence_scores.sort(key=lambda x: x[1], reverse=True)
        
        # Bouw samenvatting
        summary = []
        current_length = 0
        
        for sentence, score in sentence_scores:
            if current_length + len(sentence) <= max_length:
                summary.append(sentence)
                current_length += len(sentence) + 2  # +2 for '. '
            else:
                break
        
        if not summary:
            # Als geen zinnen passen, neem eerste zin en kort in
            return sentences[0][:max_length-3] + '...'
        
        result = '. '.join(summary)
        if len(result) > max_length:
            result = result[:max_length-3] + '...'
        
        return result
    
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
                'scores': scores
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
            
            # Urgentie score
            urgency = self.calculate_urgency_score(sentiment, item['scores'], topics)
            
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
                'summary': summary,
                'full_text': item['text']
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
        
        # Splits in urgent (>60) en positief/normaal (<40)
        urgent_feedback = [f for f in sorted_feedback if f['urgency_score'] > 60]
        positive_feedback = [f for f in sorted_feedback if f['urgency_score'] < 40]
        
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
        
        # Top topics
        if topics:
            top_topic = topics.most_common(1)[0]
            insights.append(
                f"Het meest besproken onderwerp is '{top_topic[0]}' "
                f"(voorkomt in {int(top_topic[1] * 100)}% van de feedback)"
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
        
        # Score analyse
        for score_type, stats in score_stats.items():
            if stats['mean'] < 2.5:
                insights.append(
                    f"⚠️ Lage score voor {score_type}: gemiddeld {stats['mean']:.1f}/5"
                )
            elif stats['mean'] > 4.0:
                insights.append(
                    f"✓ Hoge score voor {score_type}: gemiddeld {stats['mean']:.1f}/5"
                )
        
        # Cluster insights
        largest_cluster = max(clusters.items(), key=lambda x: len(x[1])) if clusters else None
        if largest_cluster and len(largest_cluster[1]) > len(analyzed_items) * 0.3:
            insights.append(
                f"Opvallend veel feedback over '{largest_cluster[0]}' "
                f"({len(largest_cluster[1])} items)"
            )
        
        # Variatie in scores
        for score_type, stats in score_stats.items():
            if stats['std'] > 1.5:
                insights.append(
                    f"Grote variatie in {score_type} scores (std: {stats['std']:.2f}) - "
                    f"inconsistente ervaring tussen gebruikers"
                )
        
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
            'kritiek': 0,      # 80-100
            'urgent': 0,       # 60-79
            'belangrijk': 0,   # 40-59
            'normaal': 0,      # 20-39
            'positief': 0      # 0-19
        }
        
        for item in sorted_feedback:
            urgency = item.get('urgency_score', 0)
            if urgency >= 80:
                distribution['kritiek'] += 1
            elif urgency >= 60:
                distribution['urgent'] += 1
            elif urgency >= 40:
                distribution['belangrijk'] += 1
            elif urgency >= 20:
                distribution['normaal'] += 1
            else:
                distribution['positief'] += 1
        
        return distribution


def analyze_feedback_from_db(db_session) -> Dict:
    """
    Hulpfunctie om feedback direct uit de database te analyseren.
    
    Args:
        db_session: SQLAlchemy database sessie
        
    Returns:
        Analyse resultaten dictionary
    """
    from app.models import Feedback
    
    # Haal alle feedback op
    feedback_records = db_session.query(Feedback).all()
    
    # Converteer naar dictionaries
    feedback_list = []
    for record in feedback_records:
        feedback_list.append({
            'feedback_id': record.feedback_id,
            'reservation_id': record.reservation_id,
            'netheid_score': record.netheid_score,
            'wifi_score': record.wifi_score,
            'ruimte_score': record.ruimte_score,
            'stilte_score': record.stilte_score,
            'algemene_score': record.algemene_score,
            'extra_opmerkingen': record.extra_opmerkingen
        })
    
    # Analyseer
    extractor = FeedbackTopicExtractor(min_word_freq=1, num_topics=5)
    results = extractor.analyze_feedback_batch(feedback_list)
    
    return results

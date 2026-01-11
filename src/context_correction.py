from __future__ import annotations
import re
from typing import List, Dict, Set, Optional, Tuple
from collections import defaultdict
from dataclasses import dataclass
from difflib import SequenceMatcher


@dataclass
class Context:
    """Repräsentiert den erkannten Kontext."""
    topics: Set[str]  # Erkannte Themen
    keywords: Set[str]  # Wichtige Schlüsselwörter
    domain: Optional[str] = None  # Haupt-Domain (z.B. "technik", "wetter", "allgemein")
    previous_words: List[str] = None  # Vorherige Wörter für N-Gram-Kontext
    
    def __post_init__(self):
        if self.previous_words is None:
            self.previous_words = []


class ContextDetector:
    """Erkennt Kontext aus Text."""
    
    def __init__(self, language: str = "de"):
        """
        Initialisiere Kontext-Erkenner.
        
        Args:
            language: Sprache
        """
        self.language = language
        
        # Themen-Domains mit Schlüsselwörtern
        self.domain_keywords: Dict[str, Set[str]] = {
            'technik': {
                'de': {'computer', 'rechner', 'programm', 'software', 'hardware', 'internet', 
                       'wifi', 'netzwerk', 'server', 'daten', 'datei', 'ordner', 'raspberry',
                       'pi', 'linux', 'python', 'code', 'fehler', 'bug', 'update', 'installieren'},
                'en': {'computer', 'program', 'software', 'hardware', 'internet', 'network',
                       'server', 'data', 'file', 'folder', 'raspberry', 'linux', 'python',
                       'code', 'error', 'bug', 'update', 'install'}
            },
            'wetter': {
                'de': {'wetter', 'temperatur', 'regen', 'sonne', 'wolken', 'wind', 'schnee',
                       'kalt', 'warm', 'heiß', 'kühl', 'grad', 'celsius', 'wettervorhersage'},
                'en': {'weather', 'temperature', 'rain', 'sun', 'clouds', 'wind', 'snow',
                       'cold', 'warm', 'hot', 'cool', 'degree', 'celsius', 'forecast'}
            },
            'zeit': {
                'de': {'uhr', 'zeit', 'stunde', 'minute', 'sekunde', 'tag', 'woche', 'monat',
                       'jahr', 'heute', 'morgen', 'gestern', 'jetzt', 'später', 'früher'},
                'en': {'time', 'hour', 'minute', 'second', 'day', 'week', 'month', 'year',
                       'today', 'tomorrow', 'yesterday', 'now', 'later', 'earlier'}
            },
            'einkaufen': {
                'de': {'einkaufen', 'kaufen', 'laden', 'geschäft', 'preis', 'kosten', 'geld',
                       'euro', 'bezahlen', 'warenkorb', 'bestellen', 'lieferung'},
                'en': {'shopping', 'buy', 'shop', 'store', 'price', 'cost', 'money', 'euro',
                       'dollar', 'pay', 'cart', 'order', 'delivery'}
            },
            'allgemein': {
                'de': {'hallo', 'guten', 'tag', 'morgen', 'abend', 'wie', 'geht', 'es', 'dir',
                       'danke', 'bitte', 'ja', 'nein', 'okay', 'gut', 'schlecht'},
                'en': {'hello', 'good', 'morning', 'evening', 'how', 'are', 'you', 'thanks',
                       'please', 'yes', 'no', 'okay', 'good', 'bad'}
            }
        }
        
        # Häufige Erkennungsfehler (falsch → richtig)
        self.common_errors: Dict[str, Dict[str, str]] = {
            'de': {
                'hast': 'hast',
                'hasst': 'hasst',
                'ist': 'ist',
                'isst': 'isst',
                'wird': 'wird',
                'wird': 'wird',
                'kann': 'kann',
                'kann': 'kann',
                # Technik
                'raspberry': 'raspberry',
                'raspberi': 'raspberry',
                'raspberrie': 'raspberry',
                'python': 'python',
                'piton': 'python',
                # Allgemein
                'wie': 'wie',
                'wi': 'wie',
                'geht': 'geht',
                'gehts': 'geht es',
                'gehts': 'geht\'s',
                'dir': 'dir',
                'dier': 'dir',
                'dich': 'dich',
                'dich': 'dich',
            },
            'en': {
                'the': 'the',
                'teh': 'the',
                'and': 'and',
                'nad': 'and',
                'you': 'you',
                'yu': 'you',
                'are': 'are',
                'r': 'are',
            }
        }
    
    def detect_context(self, text: str, previous_context: Optional[Context] = None) -> Context:
        """
        Erkenne Kontext aus Text.
        
        Args:
            text: Der zu analysierende Text
            previous_context: Vorheriger Kontext (für Kontinuität)
            
        Returns:
            Erkannte Kontext-Informationen
        """
        text_lower = text.lower()
        words = re.findall(r'\b\w+\b', text_lower)
        
        # Erkenne Domain basierend auf Schlüsselwörtern
        domain_scores: Dict[str, int] = defaultdict(int)
        found_keywords: Set[str] = set()
        
        for domain, keywords_dict in self.domain_keywords.items():
            keywords = keywords_dict.get(self.language, set())
            for word in words:
                if word in keywords:
                    domain_scores[domain] += 1
                    found_keywords.add(word)
        
        # Bestimme Haupt-Domain
        if domain_scores:
            main_domain = max(domain_scores.items(), key=lambda x: x[1])[0]
        else:
            main_domain = 'allgemein'
        
        # Kombiniere mit vorherigem Kontext
        if previous_context:
            topics = previous_context.topics.copy()
            keywords = previous_context.keywords.copy()
            previous_words = previous_context.previous_words.copy()
            
            # Füge neue Themen hinzu
            if main_domain != 'allgemein':
                topics.add(main_domain)
            
            # Füge neue Schlüsselwörter hinzu
            keywords.update(found_keywords)
            
            # Füge Wörter für N-Gram-Kontext hinzu (letzte 5 Wörter)
            previous_words.extend(words[-5:])
            previous_words = previous_words[-10:]  # Behalte nur letzte 10 Wörter
        else:
            topics = {main_domain} if main_domain != 'allgemein' else set()
            keywords = found_keywords
            previous_words = words[-5:]
        
        return Context(
            topics=topics,
            keywords=keywords,
            domain=main_domain,
            previous_words=previous_words
        )


class WordCorrector:
    """Korrigiert Wörter basierend auf Kontext."""
    
    def __init__(self, language: str = "de"):
        """
        Initialisiere Wort-Korrektor.
        
        Args:
            language: Sprache
        """
        self.language = language
        self.context_detector = ContextDetector(language)
        
        # Wortlisten für verschiedene Domains (für Kontext-basierte Korrektur)
        self.domain_vocabulary: Dict[str, Dict[str, Set[str]]] = {
            'technik': {
                'de': {'raspberry', 'python', 'linux', 'computer', 'programm', 'software',
                       'hardware', 'internet', 'wifi', 'netzwerk', 'server', 'daten',
                       'datei', 'ordner', 'fehler', 'bug', 'update', 'installieren'},
                'en': {'raspberry', 'python', 'linux', 'computer', 'program', 'software',
                       'hardware', 'internet', 'network', 'server', 'data', 'file', 'folder',
                       'error', 'bug', 'update', 'install'}
            },
            'wetter': {
                'de': {'wetter', 'temperatur', 'regen', 'sonne', 'wolken', 'wind', 'schnee',
                       'kalt', 'warm', 'heiß', 'kühl', 'grad', 'celsius'},
                'en': {'weather', 'temperature', 'rain', 'sun', 'clouds', 'wind', 'snow',
                       'cold', 'warm', 'hot', 'cool', 'degree', 'celsius'}
            }
        }
    
    def similarity(self, word1: str, word2: str) -> float:
        """
        Berechne Ähnlichkeit zwischen zwei Wörtern (0.0 bis 1.0).
        
        Args:
            word1: Erstes Wort
            word2: Zweites Wort
            
        Returns:
            Ähnlichkeits-Score
        """
        return SequenceMatcher(None, word1.lower(), word2.lower()).ratio()
    
    def find_similar_words(self, word: str, vocabulary: Set[str], threshold: float = 0.7) -> List[Tuple[str, float]]:
        """
        Finde ähnliche Wörter im Vokabular.
        
        Args:
            word: Das zu korrigierende Wort
            vocabulary: Vokabular für Suche
            threshold: Minimale Ähnlichkeit
            
        Returns:
            Liste von (Wort, Ähnlichkeit) Tupeln, sortiert nach Ähnlichkeit
        """
        candidates = []
        for vocab_word in vocabulary:
            sim = self.similarity(word, vocab_word)
            if sim >= threshold:
                candidates.append((vocab_word, sim))
        
        # Sortiere nach Ähnlichkeit (höchste zuerst)
        candidates.sort(key=lambda x: x[1], reverse=True)
        return candidates
    
    def correct_word(self, word: str, context: Context) -> Tuple[str, float, Optional[str]]:
        """
        Korrigiere ein Wort basierend auf Kontext.
        
        Args:
            word: Das zu korrigierende Wort
            context: Aktueller Kontext
            
        Returns:
            Tupel: (korrigiertes_wort, confidence, ursprüngliches_wort)
        """
        word_lower = word.lower()
        
        # 1. Prüfe auf bekannte Fehler
        common_errors = self.context_detector.common_errors.get(self.language, {})
        if word_lower in common_errors:
            corrected = common_errors[word_lower]
            if corrected != word_lower:
                return (corrected, 0.9, word)
        
        # 2. Kontext-basierte Korrektur
        if context.domain and context.domain in self.domain_vocabulary:
            domain_vocab = self.domain_vocabulary[context.domain].get(self.language, set())
            
            # Wenn Wort nicht im Domain-Vokabular ist, suche ähnliche
            if word_lower not in domain_vocab:
                similar = self.find_similar_words(word_lower, domain_vocab, threshold=0.75)
                if similar:
                    best_match, confidence = similar[0]
                    # Nur korrigieren, wenn Ähnlichkeit hoch genug ist
                    if confidence >= 0.85:
                        return (best_match, confidence, word)
        
        # 3. N-Gram-basierte Korrektur (wenn vorherige Wörter vorhanden)
        if context.previous_words and len(context.previous_words) >= 2:
            # Suche nach häufigen Wortkombinationen
            last_words = context.previous_words[-2:]
            # Einfache Heuristik: Wenn Wort sehr kurz und ähnlich zu häufigem Wort
            if len(word) <= 3:
                # Prüfe auf häufige Kurzwörter
                common_short = {'de': {'ist', 'der', 'die', 'das', 'und', 'oder', 'wie', 'was'},
                               'en': {'the', 'and', 'are', 'you', 'how', 'what', 'is', 'it'}}
                short_words = common_short.get(self.language, set())
                similar = self.find_similar_words(word_lower, short_words, threshold=0.8)
                if similar:
                    best_match, confidence = similar[0]
                    if confidence >= 0.9:
                        return (best_match, confidence, word)
        
        # Keine Korrektur nötig
        return (word, 1.0, None)
    
    def correct_text(self, text: str, context: Context) -> Tuple[str, List[Dict[str, str]]]:
        """
        Korrigiere Text basierend auf Kontext.
        
        Args:
            text: Der zu korrigierende Text
            context: Aktueller Kontext
            
        Returns:
            Tupel: (korrigierter_text, liste_von_korrekturen)
        """
        # Teile Text in Wörter und Satzzeichen, behalte Leerzeichen
        # Verwende ein Pattern, das Wörter, Satzzeichen und Leerzeichen erfasst
        tokens = re.findall(r'\b\w+\b|[^\w\s]|\s+', text)
        corrected_tokens = []
        corrections = []
        
        for token in tokens:
            # Prüfe, ob es ein Wort ist (nicht Leerzeichen, nicht Satzzeichen)
            if re.match(r'\b\w+\b', token):
                corrected, confidence, original = self.correct_word(token, context)
                
                if original and corrected != original:
                    corrections.append({
                        'original': original,
                        'corrected': corrected,
                        'confidence': confidence
                    })
                    corrected_tokens.append(corrected)
                else:
                    corrected_tokens.append(token)
            else:
                # Leerzeichen oder Satzzeichen - behalte wie es ist
                corrected_tokens.append(token)
        
        # Füge alle Tokens zusammen (Leerzeichen bleiben erhalten)
        corrected_text = ''.join(corrected_tokens)
        # Normalisiere mehrfache Leerzeichen zu einem
        corrected_text = re.sub(r'\s+', ' ', corrected_text).strip()
        return (corrected_text, corrections)


class ContextualSpeechCorrection:
    """Kontext-basierte Spracherkennungs-Korrektur."""
    
    def __init__(self, language: str = "de"):
        """
        Initialisiere kontext-basierte Korrektur.
        
        Args:
            language: Sprache
        """
        self.language = language
        self.context_detector = ContextDetector(language)
        self.word_corrector = WordCorrector(language)
        self.current_context: Optional[Context] = None
    
    def process_text(self, text: str) -> Tuple[str, Context, List[Dict[str, str]]]:
        """
        Verarbeite Text mit kontext-basierter Korrektur.
        
        Args:
            text: Neuer transkribierter Text
            
        Returns:
            Tupel: (korrigierter_text, kontext, liste_von_korrekturen)
        """
        # Erkenne Kontext
        context = self.context_detector.detect_context(text, self.current_context)
        
        # Korrigiere Text basierend auf Kontext
        corrected_text, corrections = self.word_corrector.correct_text(text, context)
        
        # Aktualisiere Kontext
        self.current_context = context
        
        return (corrected_text, context, corrections)
    
    def reset_context(self) -> None:
        """Setze Kontext zurück."""
        self.current_context = None

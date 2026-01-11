from __future__ import annotations
import re
from typing import List, Tuple, Optional
from dataclasses import dataclass


@dataclass
class Sentence:
    """Repräsentiert einen erkannten Satz."""
    text: str
    start_pos: int  # Position im Gesamttext
    end_pos: int
    confidence: float = 1.0  # Platzhalter für Confidence-Score
    language: Optional[str] = None  # Sprache (falls mehrsprachig)


class SentenceDetector:
    """Erkennt Satzgrenzen in transkribiertem Text."""
    
    def __init__(self, min_sentence_length: int = 3):
        """
        Initialisiere Satz-Erkenner.
        
        Args:
            min_sentence_length: Minimale Satzlänge in Zeichen
        """
        self.min_sentence_length = min_sentence_length
        
        # Satzende-Marker (Deutsch + Englisch)
        self.sentence_endings = ['.', '!', '?', '…']
        
        # Abkürzungen, die kein Satzende sind
        self.abbreviations = {
            'de': ['z.B.', 'bzw.', 'usw.', 'etc.', 'ca.', 'u.a.', 'd.h.', 'vgl.', 's.', 'S.', 
                   'Dr.', 'Prof.', 'Mr.', 'Mrs.', 'Ms.', 'Inc.', 'Ltd.', 'Co.'],
            'en': ['Mr.', 'Mrs.', 'Ms.', 'Dr.', 'Prof.', 'Inc.', 'Ltd.', 'Co.', 'e.g.', 'i.e.', 
                   'etc.', 'vs.', 'approx.', 'ca.']
        }
    
    def detect_sentences(self, text: str, language: str = "de") -> List[Sentence]:
        """
        Erkenne Sätze im Text.
        
        Args:
            text: Der zu analysierende Text
            language: Sprache für Abkürzungserkennung
            
        Returns:
            Liste von erkannten Sätzen
        """
        if not text or len(text.strip()) < self.min_sentence_length:
            return []
        
        sentences = []
        current_start = 0
        text = text.strip()
        
        # Finde Satzgrenzen
        i = 0
        while i < len(text):
            char = text[i]
            
            if char in self.sentence_endings:
                # Prüfe, ob es wirklich ein Satzende ist
                if self._is_sentence_end(text, i, language):
                    sentence_text = text[current_start:i+1].strip()
                    
                    if len(sentence_text) >= self.min_sentence_length:
                        sentences.append(Sentence(
                            text=sentence_text,
                            start_pos=current_start,
                            end_pos=i+1
                        ))
                    
                    # Nächster Satz beginnt nach Leerzeichen
                    i += 1
                    while i < len(text) and text[i] in [' ', '\n', '\t']:
                        i += 1
                    current_start = i
                    continue
            
            i += 1
        
        # Letzter Satz (falls kein Satzende vorhanden)
        if current_start < len(text):
            remaining = text[current_start:].strip()
            if len(remaining) >= self.min_sentence_length:
                sentences.append(Sentence(
                    text=remaining,
                    start_pos=current_start,
                    end_pos=len(text)
                ))
        
        return sentences
    
    def _is_sentence_end(self, text: str, pos: int, language: str) -> bool:
        """
        Prüfe, ob die Position wirklich ein Satzende ist.
        
        Args:
            text: Gesamttext
            pos: Position des Satzende-Zeichens
            language: Sprache
            
        Returns:
            True wenn es ein Satzende ist
        """
        # Prüfe auf Abkürzungen
        # Schaue 5 Zeichen vor dem Satzende
        start = max(0, pos - 10)
        context = text[start:pos+1]
        
        for abbrev in self.abbreviations.get(language, []):
            if context.endswith(abbrev):
                return False
        
        # Prüfe, ob nach dem Satzende ein Großbuchstabe folgt (typisch für neuen Satz)
        if pos + 1 < len(text):
            next_char = text[pos + 1]
            if next_char == ' ' and pos + 2 < len(text):
                next_next = text[pos + 2]
                if next_next.isupper():
                    return True
        
        # Wenn direkt nach Punkt ein Leerzeichen und dann Großbuchstabe
        if pos + 1 < len(text) and text[pos + 1] == ' ':
            if pos + 2 < len(text) and text[pos + 2].isupper():
                return True
        
        # Fallback: Wenn Punkt am Ende des Textes oder vor Leerzeichen
        if pos == len(text) - 1:
            return True
        
        return True  # Standard: behandele als Satzende
    
    def get_latest_sentence(self, text: str, language: str = "de") -> Optional[Sentence]:
        """
        Hole den neuesten/letzten vollständigen Satz.
        
        Args:
            text: Gesamttext
            language: Sprache
            
        Returns:
            Letzter vollständiger Satz oder None
        """
        sentences = self.detect_sentences(text, language)
        if sentences:
            return sentences[-1]
        return None
    
    def get_incomplete_sentence(self, text: str) -> Optional[str]:
        """
        Hole den unvollständigen Satz am Ende (ohne Satzende).
        
        Args:
            text: Gesamttext
            
        Returns:
            Unvollständiger Satz oder None
        """
        sentences = self.detect_sentences(text)
        if not sentences:
            return text.strip() if text.strip() else None
        
        last_sentence = sentences[-1]
        if last_sentence.end_pos < len(text.strip()):
            # Es gibt Text nach dem letzten Satz
            incomplete = text[last_sentence.end_pos:].strip()
            return incomplete if incomplete else None
        
        return None


class SemanticAnalyzer:
    """Einfache semantische Analyse von Sätzen."""
    
    def __init__(self):
        """Initialisiere semantischen Analyzer."""
        # Fragewörter (Deutsch + Englisch)
        self.question_words = {
            'de': ['wer', 'was', 'wo', 'wann', 'warum', 'wie', 'welche', 'welcher', 'welches', 
                   'woher', 'wohin', 'womit', 'wodurch', 'wofür', 'wogegen'],
            'en': ['who', 'what', 'where', 'when', 'why', 'how', 'which', 'whose', 'whom']
        }
        
        # Imperativ-Marker
        self.imperative_markers = {
            'de': ['bitte', 'mach', 'tue', 'gib', 'zeig', 'sag', 'erkläre', 'hilf'],
            'en': ['please', 'make', 'do', 'give', 'show', 'tell', 'explain', 'help']
        }
    
    def analyze_sentence(self, sentence: Sentence, language: str = "de") -> dict:
        """
        Analysiere einen Satz semantisch.
        
        Args:
            sentence: Der zu analysierende Satz
            language: Sprache
            
        Returns:
            Dictionary mit semantischen Informationen
        """
        text_lower = sentence.text.lower()
        
        result = {
            'is_question': False,
            'is_imperative': False,
            'is_exclamation': False,
            'is_statement': False,
            'question_type': None,
            'sentiment': 'neutral',  # neutral, positive, negative
            'keywords': []
        }
        
        # Frage-Erkennung
        if sentence.text.strip().endswith('?'):
            result['is_question'] = True
            for qw in self.question_words.get(language, []):
                if text_lower.startswith(qw) or f' {qw} ' in text_lower:
                    result['question_type'] = qw
                    break
        
        # Imperativ-Erkennung
        for marker in self.imperative_markers.get(language, []):
            if text_lower.startswith(marker) or f' {marker} ' in text_lower:
                result['is_imperative'] = True
                break
        
        # Ausruf-Erkennung
        if sentence.text.strip().endswith('!'):
            result['is_exclamation'] = True
        
        # Statement (wenn nichts anderes)
        if not (result['is_question'] or result['is_imperative'] or result['is_exclamation']):
            result['is_statement'] = True
        
        # Einfache Sentiment-Erkennung
        positive_words = {
            'de': ['gut', 'super', 'toll', 'wunderbar', 'perfekt', 'ja', 'okay', 'ok'],
            'en': ['good', 'great', 'wonderful', 'perfect', 'yes', 'okay', 'ok']
        }
        negative_words = {
            'de': ['schlecht', 'nein', 'nicht', 'falsch', 'fehler', 'problem'],
            'en': ['bad', 'no', 'not', 'wrong', 'error', 'problem']
        }
        
        for word in positive_words.get(language, []):
            if word in text_lower:
                result['sentiment'] = 'positive'
                break
        
        if result['sentiment'] == 'neutral':
            for word in negative_words.get(language, []):
                if word in text_lower:
                    result['sentiment'] = 'negative'
                    break
        
        return result
    
    def get_sentence_type(self, sentence: Sentence, language: str = "de") -> str:
        """
        Bestimme den Satztyp.
        
        Args:
            sentence: Der Satz
            language: Sprache
            
        Returns:
            Satztyp: "question", "imperative", "exclamation", "statement"
        """
        analysis = self.analyze_sentence(sentence, language)
        
        if analysis['is_question']:
            return "question"
        elif analysis['is_imperative']:
            return "imperative"
        elif analysis['is_exclamation']:
            return "exclamation"
        else:
            return "statement"


class SemanticSpeechRecognition:
    """Spracherkennung mit semantischer Satzerkennung."""
    
    def __init__(self, language: str = "de"):
        """
        Initialisiere semantische Spracherkennung.
        
        Args:
            language: Sprache für Analyse
        """
        self.language = language
        self.sentence_detector = SentenceDetector()
        self.semantic_analyzer = SemanticAnalyzer()
        self.complete_sentences: List[Sentence] = []
        self.incomplete_sentence: Optional[str] = None
    
    def process_text(self, new_text: str) -> dict:
        """
        Verarbeite neuen Text und erkenne Sätze semantisch.
        
        Args:
            new_text: Neuer transkribierter Text
            
        Returns:
            Dictionary mit:
            - complete_sentences: Liste vollständiger Sätze
            - incomplete_sentence: Unvollständiger Satz
            - new_sentences: Neu erkannte Sätze
            - semantic_info: Semantische Informationen
        """
        # Erkenne Sätze im neuen Text
        sentences = self.sentence_detector.detect_sentences(new_text, self.language)
        
        # Finde neue Sätze (die noch nicht in complete_sentences sind)
        new_sentences = []
        for sentence in sentences:
            # Prüfe, ob dieser Satz bereits bekannt ist
            is_new = True
            for existing in self.complete_sentences:
                if existing.text == sentence.text:
                    is_new = False
                    break
            
            if is_new:
                new_sentences.append(sentence)
                self.complete_sentences.append(sentence)
        
        # Unvollständiger Satz
        incomplete = self.sentence_detector.get_incomplete_sentence(new_text)
        self.incomplete_sentence = incomplete
        
        # Semantische Analyse für neue Sätze
        semantic_info = []
        for sentence in new_sentences:
            analysis = self.semantic_analyzer.analyze_sentence(sentence, self.language)
            semantic_info.append({
                'sentence': sentence,
                'analysis': analysis,
                'type': self.semantic_analyzer.get_sentence_type(sentence, self.language)
            })
        
        return {
            'complete_sentences': self.complete_sentences,
            'incomplete_sentence': self.incomplete_sentence,
            'new_sentences': new_sentences,
            'semantic_info': semantic_info,
            'full_text': new_text
        }
    
    def get_display_text(self, max_sentences: int = 2) -> str:
        """
        Hole Text für Display-Anzeige (letzte N Sätze).
        
        Args:
            max_sentences: Maximale Anzahl anzuzeigender Sätze
            
        Returns:
            Text für Display
        """
        if not self.complete_sentences and not self.incomplete_sentence:
            return ""
        
        # Nimm die letzten N vollständigen Sätze
        display_sentences = self.complete_sentences[-max_sentences:] if self.complete_sentences else []
        
        # Füge unvollständigen Satz hinzu
        text_parts = [s.text for s in display_sentences]
        if self.incomplete_sentence:
            text_parts.append(self.incomplete_sentence)
        
        return " ".join(text_parts)
    
    def reset(self) -> None:
        """Setze alle Sätze zurück."""
        self.complete_sentences = []
        self.incomplete_sentence = None

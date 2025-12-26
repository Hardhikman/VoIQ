//! MCQ question generation for vocabulary quiz

use pyo3::prelude::*;
use rand::seq::SliceRandom;
use rand::Rng;
use rusqlite::Connection;
use crate::db::{Word, get_all_words, get_word_by_id};

/// MCQ Question with 4 options
#[pyclass]
#[derive(Debug, Clone)]
pub struct MCQQuestion {
    #[pyo3(get)]
    pub word_id: i64,
    #[pyo3(get)]
    pub question_type: String,
    #[pyo3(get)]
    pub question_text: String,
    #[pyo3(get)]
    pub options: Vec<String>,
    #[pyo3(get)]
    pub correct_index: usize,
    #[pyo3(get)]
    pub correct_answer: String,
}

#[pymethods]
impl MCQQuestion {
    fn __repr__(&self) -> String {
        format!("MCQQuestion(type='{}', question='{}...')", 
                self.question_type, &self.question_text.chars().take(40).collect::<String>())
    }
}

/// Get random item from comma-separated list
fn get_random_item(csv: &str) -> String {
    let items: Vec<&str> = csv.split(',')
        .map(|s| s.trim())
        .filter(|s| !s.is_empty())
        .collect();
    
    if items.is_empty() {
        return String::new();
    }
    
    let mut rng = rand::thread_rng();
    let idx = rng.gen_range(0..items.len());
    items[idx].to_string()
}

/// Get the field value for creating distractors
fn get_field_for_type(word: &Word, q_type: &str) -> String {
    match q_type {
        "word_to_meaning" | "synonym_to_meaning" | "antonym_to_meaning" => word.meaning.clone(),
        "meaning_to_word" | "synonym_to_word" | "antonym_to_word" => word.word.clone(),
        "word_to_synonym" | "meaning_to_synonym" | "antonym_to_synonym" => get_random_item(&word.synonyms),
        "word_to_antonym" | "meaning_to_antonym" | "synonym_to_antonym" => get_random_item(&word.antonyms),
        _ => word.meaning.clone(),
    }
}

/// Generate an MCQ question for a given word
pub fn generate_mcq(db_path: &str, word_id: i64, question_type: &str) -> Result<MCQQuestion, String> {
    let conn = Connection::open(db_path)
        .map_err(|e| format!("Failed to open database: {}", e))?;
    
    let target = get_word_by_id(&conn, word_id)
        .map_err(|e| format!("Failed to get word: {}", e))?
        .ok_or("Word not found")?;
    
    let all_words = get_all_words(&conn)
        .map_err(|e| format!("Failed to get all words: {}", e))?;
    
    if all_words.len() < 4 {
        return Err("Not enough words for MCQ generation (need at least 4)".to_string());
    }
    
    let mut rng = rand::thread_rng();
    
    // Build question text and get correct answer
    let (question_text, correct_answer) = match question_type {
        "word_to_meaning" => (
            format!("What is the meaning of '{}'?", target.word),
            target.meaning.clone(),
        ),
        "meaning_to_word" => (
            format!("Which word means: '{}'?", &target.meaning.chars().take(100).collect::<String>()),
            target.word.clone(),
        ),
        "word_to_synonym" => (
            format!("Which is a synonym of '{}'?", target.word),
            get_random_item(&target.synonyms),
        ),
        "word_to_antonym" => (
            format!("Which is an antonym of '{}'?", target.word),
            get_random_item(&target.antonyms),
        ),
        "synonym_to_word" => (
            format!("Which word has the synonym '{}'?", get_random_item(&target.synonyms)),
            target.word.clone(),
        ),
        "antonym_to_word" => (
            format!("Which word has the antonym '{}'?", get_random_item(&target.antonyms)),
            target.word.clone(),
        ),
        "synonym_to_meaning" => (
            format!("What is the meaning of the word with synonym '{}'?", get_random_item(&target.synonyms)),
            target.meaning.clone(),
        ),
        "antonym_to_meaning" => (
            format!("What is the meaning of the word with antonym '{}'?", get_random_item(&target.antonyms)),
            target.meaning.clone(),
        ),
        "meaning_to_synonym" => (
            format!("Which is a synonym of the word meaning: '{}'?", &target.meaning.chars().take(80).collect::<String>()),
            get_random_item(&target.synonyms),
        ),
        "meaning_to_antonym" => (
            format!("Which is an antonym of the word meaning: '{}'?", &target.meaning.chars().take(80).collect::<String>()),
            get_random_item(&target.antonyms),
        ),
        "synonym_to_antonym" => (
            format!("Which is an antonym of the word with synonym '{}'?", get_random_item(&target.synonyms)),
            get_random_item(&target.antonyms),
        ),
        "antonym_to_synonym" => (
            format!("Which is a synonym of the word with antonym '{}'?", get_random_item(&target.antonyms)),
            get_random_item(&target.synonyms),
        ),
        _ => return Err(format!("Unknown question type: {}", question_type)),
    };
    
    if correct_answer.is_empty() {
        return Err(format!("Missing data for question type: {}", question_type));
    }
    
    // Collect distractors from other words
    let mut distractors: Vec<String> = all_words
        .iter()
        .filter(|w| w.id != target.id)
        .map(|w| get_field_for_type(w, question_type))
        .filter(|s| !s.is_empty() && s != &correct_answer)
        .collect();
    
    distractors.shuffle(&mut rng);
    distractors.truncate(3);
    
    if distractors.len() < 3 {
        return Err("Not enough unique distractors for MCQ".to_string());
    }
    
    // Build options list with correct answer in random position
    let correct_index = rng.gen_range(0..4);
    let mut options = distractors;
    options.insert(correct_index, correct_answer.clone());
    
    Ok(MCQQuestion {
        word_id: target.id,
        question_type: question_type.to_string(),
        question_text,
        options,
        correct_index,
        correct_answer,
    })
}

// ============= Python Binding =============

#[pyfunction]
#[pyo3(name = "generate_mcq")]
pub fn py_generate_mcq(db_path: &str, word_id: i64, question_type: &str) -> PyResult<MCQQuestion> {
    generate_mcq(db_path, word_id, question_type)
        .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e))
}

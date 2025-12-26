//! Fuzzy string matching for dictation scoring

use pyo3::prelude::*;
use strsim::{levenshtein, normalized_levenshtein, jaro_winkler};

/// Result of fuzzy matching comparison
#[pyclass]
#[derive(Debug, Clone)]
pub struct MatchResult {
    #[pyo3(get)]
    pub is_correct: bool,
    #[pyo3(get)]
    pub similarity_score: f64,
    #[pyo3(get)]
    pub feedback: String,
}

#[pymethods]
impl MatchResult {
    fn __repr__(&self) -> String {
        format!("MatchResult(is_correct={}, score={:.2}, feedback='{}')", 
                self.is_correct, self.similarity_score, self.feedback)
    }
}

/// Check if user input matches expected answer with fuzzy matching
pub fn check_match(user_input: &str, expected: &str, threshold: f64) -> MatchResult {
    let input_normalized = user_input.trim().to_lowercase();
    let expected_normalized = expected.trim().to_lowercase();
    
    // Exact match
    if input_normalized == expected_normalized {
        return MatchResult {
            is_correct: true,
            similarity_score: 1.0,
            feedback: "Perfect! ✓".to_string(),
        };
    }
    
    // Calculate similarity using multiple algorithms
    let levenshtein_sim = normalized_levenshtein(&input_normalized, &expected_normalized);
    let jaro_sim = jaro_winkler(&input_normalized, &expected_normalized);
    
    // Weighted average (Jaro-Winkler is better for typos)
    let similarity = (levenshtein_sim * 0.4 + jaro_sim * 0.6);
    
    let (is_correct, feedback) = if similarity >= threshold {
        (true, format!("Close enough! ✓ ({}% match)", (similarity * 100.0) as i32))
    } else if similarity >= 0.5 {
        let distance = levenshtein(&input_normalized, &expected_normalized);
        (false, format!("Almost! {} characters off. Expected: '{}'", distance, expected))
    } else {
        (false, format!("Incorrect. Expected: '{}'", expected))
    };
    
    MatchResult {
        is_correct,
        similarity_score: similarity,
        feedback,
    }
}

// ============= Python Binding =============

#[pyfunction]
#[pyo3(name = "check_match")]
pub fn py_check_match(user_input: &str, expected: &str, threshold: Option<f64>) -> MatchResult {
    check_match(user_input, expected, threshold.unwrap_or(0.8))
}

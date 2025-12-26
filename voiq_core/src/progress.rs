//! Progress tracking - attempts storage and statistics

use pyo3::prelude::*;
use rusqlite::{Connection, params};
use crate::db::Word;

/// Attempt statistics for a user
#[pyclass]
#[derive(Debug, Clone)]
pub struct AttemptStats {
    #[pyo3(get)]
    pub total_attempts: i64,
    #[pyo3(get)]
    pub correct_count: i64,
    #[pyo3(get)]
    pub incorrect_count: i64,
    #[pyo3(get)]
    pub accuracy_percent: f64,
}

#[pymethods]
impl AttemptStats {
    fn __repr__(&self) -> String {
        format!("AttemptStats(total={}, correct={}, accuracy={:.1}%)", 
                self.total_attempts, self.correct_count, self.accuracy_percent)
    }
}

/// Save an attempt to the database
pub fn save_attempt(
    db_path: &str,
    word_id: i64,
    mode: &str,
    question_type: &str,
    is_correct: bool,
    user_answer: &str,
    expected_answer: &str,
    time_taken_ms: Option<i64>,
) -> Result<(), String> {
    let conn = Connection::open(db_path)
        .map_err(|e| format!("Failed to open database: {}", e))?;
    
    conn.execute(
        "INSERT INTO attempts (word_id, mode, question_type, is_correct, user_answer, expected_answer, time_taken_ms) 
         VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7)",
        params![word_id, mode, question_type, is_correct as i32, user_answer, expected_answer, time_taken_ms],
    ).map_err(|e| format!("Failed to save attempt: {}", e))?;
    
    Ok(())
}

/// Get words that have been answered incorrectly, sorted by fail count
pub fn get_failed_words(db_path: &str, limit: Option<usize>) -> Result<Vec<(Word, i64)>, String> {
    let conn = Connection::open(db_path)
        .map_err(|e| format!("Failed to open database: {}", e))?;
    
    let limit_clause = limit.map(|l| format!(" LIMIT {}", l)).unwrap_or_default();
    
    let query = format!(
        "SELECT v.id, v.word, v.meaning, v.synonyms, v.antonyms, COALESCE(v.category, 'Default'), COUNT(*) as fail_count
         FROM vocabulary v
         JOIN attempts a ON v.id = a.word_id
         WHERE a.is_correct = 0
         GROUP BY v.id
         ORDER BY fail_count DESC{}",
        limit_clause
    );
    
    let mut stmt = conn.prepare(&query)
        .map_err(|e| format!("Failed to prepare query: {}", e))?;
    
    let results = stmt.query_map([], |row| {
        Ok((
            Word {
                id: row.get(0)?,
                word: row.get(1)?,
                meaning: row.get(2)?,
                synonyms: row.get::<_, Option<String>>(3)?.unwrap_or_default(),
                antonyms: row.get::<_, Option<String>>(4)?.unwrap_or_default(),
                category: row.get::<_, Option<String>>(5)?.unwrap_or_else(|| "Default".to_string()),
            },
            row.get::<_, i64>(6)?,
        ))
    }).map_err(|e| format!("Failed to execute query: {}", e))?;
    
    let failed: Vec<(Word, i64)> = results.filter_map(|r| r.ok()).collect();
    Ok(failed)
}

/// Get overall statistics
pub fn get_stats(db_path: &str) -> Result<AttemptStats, String> {
    let conn = Connection::open(db_path)
        .map_err(|e| format!("Failed to open database: {}", e))?;
    
    let mut stmt = conn.prepare(
        "SELECT COUNT(*) as total, SUM(is_correct) as correct FROM attempts"
    ).map_err(|e| format!("Failed to prepare query: {}", e))?;
    
    let stats = stmt.query_row([], |row| {
        let total: i64 = row.get(0)?;
        let correct: i64 = row.get::<_, Option<i64>>(1)?.unwrap_or(0);
        let incorrect = total - correct;
        let accuracy = if total > 0 { (correct as f64 / total as f64) * 100.0 } else { 0.0 };
        
        Ok(AttemptStats {
            total_attempts: total,
            correct_count: correct,
            incorrect_count: incorrect,
            accuracy_percent: accuracy,
        })
    }).map_err(|e| format!("Failed to get stats: {}", e))?;
    
    Ok(stats)
}

// ============= Python Bindings =============

#[pyfunction]
#[pyo3(name = "save_attempt")]
pub fn py_save_attempt(
    db_path: &str,
    word_id: i64,
    mode: &str,
    question_type: &str,
    is_correct: bool,
    user_answer: &str,
    expected_answer: &str,
    time_taken_ms: Option<i64>,
) -> PyResult<()> {
    save_attempt(db_path, word_id, mode, question_type, is_correct, user_answer, expected_answer, time_taken_ms)
        .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e))
}

#[pyfunction]
#[pyo3(name = "get_failed_words")]
pub fn py_get_failed_words(db_path: &str, limit: Option<usize>) -> PyResult<Vec<(Word, i64)>> {
    get_failed_words(db_path, limit)
        .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e))
}

#[pyfunction]
#[pyo3(name = "get_stats")]
pub fn py_get_stats(db_path: &str) -> PyResult<AttemptStats> {
    get_stats(db_path)
        .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e))
}

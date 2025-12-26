//! VoIQ Core - High-performance Rust module for vocabulary quiz system
//! 
//! Provides SQLite database operations, Excel parsing, fuzzy matching, and MCQ generation.

mod db;
mod excel;
mod fuzzy;
mod questions;
mod progress;

use pyo3::prelude::*;

// Re-export structs for Python
pub use db::{Word, CategoryInfo, init_database, load_vocabulary, get_words, get_word_by_id, get_all_words, get_categories, delete_category};
pub use excel::parse_excel;
pub use fuzzy::{check_match, MatchResult};
pub use questions::{generate_mcq, MCQQuestion};
pub use progress::{save_attempt, get_failed_words, get_stats, AttemptStats};

/// VoIQ Core Python Module
#[pymodule]
fn voiq_core(m: &Bound<'_, PyModule>) -> PyResult<()> {
    // Database functions
    m.add_function(wrap_pyfunction!(db::py_init_database, m)?)?;
    m.add_function(wrap_pyfunction!(db::py_get_all_words, m)?)?;
    m.add_function(wrap_pyfunction!(db::py_get_words_by_order, m)?)?;
    m.add_function(wrap_pyfunction!(db::py_get_word_by_id, m)?)?;
    m.add_function(wrap_pyfunction!(db::py_add_word, m)?)?;
    m.add_function(wrap_pyfunction!(db::py_get_categories, m)?)?;
    m.add_function(wrap_pyfunction!(db::py_delete_category, m)?)?;
    
    // File parsing (Excel and CSV)
    m.add_function(wrap_pyfunction!(excel::py_parse_excel, m)?)?;
    m.add_function(wrap_pyfunction!(excel::py_parse_csv, m)?)?;
    
    // Fuzzy matching
    m.add_function(wrap_pyfunction!(fuzzy::py_check_match, m)?)?;
    
    // Question generation
    m.add_function(wrap_pyfunction!(questions::py_generate_mcq, m)?)?;
    
    // Progress tracking
    m.add_function(wrap_pyfunction!(progress::py_save_attempt, m)?)?;
    m.add_function(wrap_pyfunction!(progress::py_get_failed_words, m)?)?;
    m.add_function(wrap_pyfunction!(progress::py_get_stats, m)?)?;
    
    // Register classes
    m.add_class::<db::Word>()?;
    m.add_class::<db::CategoryInfo>()?;
    m.add_class::<fuzzy::MatchResult>()?;
    m.add_class::<questions::MCQQuestion>()?;
    m.add_class::<progress::AttemptStats>()?;
    
    Ok(())
}


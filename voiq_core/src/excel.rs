//! File parsing for VoIQ vocabulary import (Excel and CSV)

use pyo3::prelude::*;
use calamine::{Reader, open_workbook, Xlsx, Data};
use csv::ReaderBuilder;
use crate::db::Word;
use rusqlite::Connection;
use std::path::Path;

/// Parse file (Excel or CSV) and load into database with category
pub fn parse_file(file_path: &str, db_path: &str, category: &str) -> Result<usize, String> {
    let path = Path::new(file_path);
    let extension = path.extension()
        .and_then(|e| e.to_str())
        .map(|e| e.to_lowercase())
        .unwrap_or_default();
    
    match extension.as_str() {
        "xlsx" | "xls" => parse_excel(file_path, db_path, category),
        "csv" => parse_csv(file_path, db_path, category),
        _ => Err(format!("Unsupported file format: .{}", extension)),
    }
}

/// Column index mapping
#[derive(Debug, Default, Clone)]
pub struct ColumnMapping {
    pub word: usize,
    pub meaning: Option<usize>,
    pub synonyms: Option<usize>,
    pub antonyms: Option<usize>,
}

/// Detect column indices from header names
fn detect_columns(headers: &[String]) -> Result<ColumnMapping, String> {
    let mut mapping = ColumnMapping::default();
    let mut word_found = false;
    
    for (i, header) in headers.iter().enumerate() {
        match header.to_lowercase().trim() {
            "word" | "words" | "vocabulary" => {
                mapping.word = i;
                word_found = true;
            }
            "meaning" | "meanings" | "definition" | "definitions" => mapping.meaning = Some(i),
            "synonym" | "synonyms" => mapping.synonyms = Some(i),
            "antonym" | "antonyms" => mapping.antonyms = Some(i),
            _ => {} // Unknown columns ignored
        }
    }
    
    // Validate: Word column is required
    if !word_found {
        return Err("Missing required 'Word' column in file header".to_string());
    }
    
    // Validate: At least one other column required
    if mapping.meaning.is_none() && mapping.synonyms.is_none() && mapping.antonyms.is_none() {
        return Err("At least one additional column required (Meaning, Synonyms, or Antonyms)".to_string());
    }
    
    Ok(mapping)
}

/// Parse Excel file and load into database with category
pub fn parse_excel(file_path: &str, db_path: &str, category: &str) -> Result<usize, String> {
    let mut workbook: Xlsx<_> = open_workbook(file_path)
        .map_err(|e| format!("Failed to open Excel file: {}", e))?;
    
    let sheet_name = workbook.sheet_names().first()
        .ok_or("No sheets found in Excel file")?
        .clone();
    
    let range = workbook.worksheet_range(&sheet_name)
        .map_err(|e| format!("Failed to read sheet: {}", e))?;
    
    let mut words = Vec::new();
    let mut rows = range.rows();
    
    // Parse header row to detect column mapping
    let header_row = rows.next().ok_or("Empty file - no header row")?;
    let headers: Vec<String> = header_row.iter().map(get_cell_string).collect();
    let mapping = detect_columns(&headers)?;
    
    for row in rows {
        let row_len = row.len();
        let word_val = if mapping.word < row_len { get_cell_string(&row[mapping.word]) } else { String::new() };
        let meaning_val = mapping.meaning.filter(|&i| i < row_len).map(|i| get_cell_string(&row[i])).unwrap_or_default();
        let synonyms_val = mapping.synonyms.filter(|&i| i < row_len).map(|i| get_cell_string(&row[i])).unwrap_or_default();
        let antonyms_val = mapping.antonyms.filter(|&i| i < row_len).map(|i| get_cell_string(&row[i])).unwrap_or_default();
        
        if !word_val.is_empty() {
            words.push(Word {
                id: 0,
                word: word_val,
                meaning: meaning_val,
                synonyms: synonyms_val,
                antonyms: antonyms_val,
                category: String::new(),
            });
        }
    }
    
    save_words_to_db(db_path, words, category)
}

/// Parse CSV file and load into database with category
pub fn parse_csv(file_path: &str, db_path: &str, category: &str) -> Result<usize, String> {
    let mut reader = ReaderBuilder::new()
        .has_headers(true)
        .flexible(true)
        .from_path(file_path)
        .map_err(|e| format!("Failed to open CSV file: {}", e))?;
    
    // Parse header row to detect column mapping
    let headers: Vec<String> = reader.headers()
        .map_err(|e| format!("Failed to read CSV headers: {}", e))?
        .iter()
        .map(|s| s.to_string())
        .collect();
    let mapping = detect_columns(&headers)?;
    
    let mut words = Vec::new();
    
    for result in reader.records() {
        let record = result.map_err(|e| format!("Failed to read CSV row: {}", e))?;
        let row_len = record.len();
        
        let word_val = if mapping.word < row_len { record.get(mapping.word).unwrap_or("").trim().to_string() } else { String::new() };
        let meaning_val = mapping.meaning.filter(|&i| i < row_len).map(|i| record.get(i).unwrap_or("").trim().to_string()).unwrap_or_default();
        let synonyms_val = mapping.synonyms.filter(|&i| i < row_len).map(|i| record.get(i).unwrap_or("").trim().to_string()).unwrap_or_default();
        let antonyms_val = mapping.antonyms.filter(|&i| i < row_len).map(|i| record.get(i).unwrap_or("").trim().to_string()).unwrap_or_default();
        
        if !word_val.is_empty() {
            words.push(Word {
                id: 0,
                word: word_val,
                meaning: meaning_val,
                synonyms: synonyms_val,
                antonyms: antonyms_val,
                category: String::new(),
            });
        }
    }
    
    save_words_to_db(db_path, words, category)
}

/// Save words to database with category (shared by Excel and CSV parsers)
fn save_words_to_db(db_path: &str, words: Vec<Word>, category: &str) -> Result<usize, String> {
    let conn = Connection::open(db_path)
        .map_err(|e| format!("Failed to open database: {}", e))?;
    
    // Initialize database
    crate::db::init_database(db_path)
        .map_err(|e| format!("Failed to init database: {}", e))?;
    
    // Note: No longer clearing all vocabulary - just adding to the category
    // To replace a category, delete it first then re-upload
    
    let count = crate::db::load_vocabulary(&conn, words, category)
        .map_err(|e| format!("Failed to load vocabulary: {}", e))?;
    
    Ok(count)
}

/// Helper to extract string from Excel cell
fn get_cell_string(cell: &Data) -> String {
    match cell {
        Data::String(s) => s.trim().to_string(),
        Data::Int(i) => i.to_string(),
        Data::Float(f) => f.to_string(),
        Data::Bool(b) => b.to_string(),
        Data::DateTime(dt) => dt.to_string(),
        Data::DateTimeIso(s) => s.clone(),
        Data::DurationIso(s) => s.clone(),
        Data::Error(_) => String::new(),
        Data::Empty => String::new(),
    }
}

// ============= Python Bindings =============

#[pyfunction]
#[pyo3(name = "parse_excel")]
pub fn py_parse_excel(file_path: &str, db_path: &str, category: Option<&str>) -> PyResult<usize> {
    let cat = category.unwrap_or("Default");
    parse_file(file_path, db_path, cat)
        .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e))
}

#[pyfunction]
#[pyo3(name = "parse_csv")]
pub fn py_parse_csv(file_path: &str, db_path: &str, category: Option<&str>) -> PyResult<usize> {
    let cat = category.unwrap_or("Default");
    parse_csv(file_path, db_path, cat)
        .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e))
}

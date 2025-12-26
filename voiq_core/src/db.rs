//! Database operations for VoIQ vocabulary storage

use pyo3::prelude::*;
use rusqlite::{Connection, Result as SqliteResult, params};
use serde::{Deserialize, Serialize};
use std::path::Path;

/// Word entry from vocabulary database
#[pyclass]
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Word {
    #[pyo3(get)]
    pub id: i64,
    #[pyo3(get)]
    pub word: String,
    #[pyo3(get)]
    pub meaning: String,
    #[pyo3(get)]
    pub synonyms: String,
    #[pyo3(get)]
    pub antonyms: String,
    #[pyo3(get)]
    pub category: String,
}

#[pymethods]
impl Word {
    fn __repr__(&self) -> String {
        format!("Word(id={}, word='{}', category='{}')", 
                self.id, self.word, self.category)
    }
}

/// Category info with word count
#[pyclass]
#[derive(Debug, Clone)]
pub struct CategoryInfo {
    #[pyo3(get)]
    pub name: String,
    #[pyo3(get)]
    pub word_count: i64,
}

/// Initialize database with schema
pub fn init_database(db_path: &str) -> SqliteResult<Connection> {
    let conn = Connection::open(db_path)?;
    
    conn.execute(
        "CREATE TABLE IF NOT EXISTS vocabulary (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            word TEXT NOT NULL,
            meaning TEXT NOT NULL,
            synonyms TEXT,
            antonyms TEXT,
            category TEXT DEFAULT 'Default',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )",
        [],
    )?;
    
    // Add category column if it doesn't exist (migration for existing DBs)
    let _ = conn.execute("ALTER TABLE vocabulary ADD COLUMN category TEXT DEFAULT 'Default'", []);
    
    conn.execute(
        "CREATE TABLE IF NOT EXISTS attempts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            word_id INTEGER REFERENCES vocabulary(id),
            mode TEXT NOT NULL,
            question_type TEXT NOT NULL,
            is_correct INTEGER NOT NULL,
            user_answer TEXT,
            expected_answer TEXT,
            time_taken_ms INTEGER,
            attempted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )",
        [],
    )?;
    
    Ok(conn)
}

/// Load vocabulary from parsed Excel data with category
pub fn load_vocabulary(conn: &Connection, words: Vec<Word>, category: &str) -> SqliteResult<usize> {
    let mut count = 0;
    for word in words {
        conn.execute(
            "INSERT INTO vocabulary (word, meaning, synonyms, antonyms, category) VALUES (?1, ?2, ?3, ?4, ?5)",
            params![word.word, word.meaning, word.synonyms, word.antonyms, category],
        )?;
        count += 1;
    }
    Ok(count)
}

/// Get words with ordering and optional category filter
pub fn get_words(conn: &Connection, order: &str, letter: Option<char>, categories: Option<Vec<String>>) -> SqliteResult<Vec<Word>> {
    let base_query = "SELECT id, word, meaning, synonyms, antonyms, COALESCE(category, 'Default') FROM vocabulary";
    
    let mut conditions = Vec::new();
    
    // Category filter
    if let Some(ref cats) = categories {
        if !cats.is_empty() {
            let cat_list: Vec<String> = cats.iter().map(|c| format!("'{}'", c.replace("'", "''"))).collect();
            conditions.push(format!("category IN ({})", cat_list.join(", ")));
        }
    }
    
    // Letter filter
    if let Some(c) = letter {
        conditions.push(format!("LOWER(word) LIKE '{}%'", c.to_lowercase()));
    }
    
    let where_clause = if conditions.is_empty() {
        String::new()
    } else {
        format!(" WHERE {}", conditions.join(" AND "))
    };
    
    let order_clause = match order.to_lowercase().as_str() {
        "a_to_z" => " ORDER BY word ASC",
        "z_to_a" => " ORDER BY word DESC",
        "random" => " ORDER BY RANDOM()",
        _ => " ORDER BY word ASC",
    };
    
    let query = format!("{}{}{}", base_query, where_clause, order_clause);
    
    let mut stmt = conn.prepare(&query)?;
    let word_iter = stmt.query_map([], |row| {
        Ok(Word {
            id: row.get(0)?,
            word: row.get(1)?,
            meaning: row.get(2)?,
            synonyms: row.get::<_, Option<String>>(3)?.unwrap_or_default(),
            antonyms: row.get::<_, Option<String>>(4)?.unwrap_or_default(),
            category: row.get::<_, Option<String>>(5)?.unwrap_or_else(|| "Default".to_string()),
        })
    })?;
    
    let words: Vec<Word> = word_iter.filter_map(|w| w.ok()).collect();
    Ok(words)
}

/// Get single word by ID
pub fn get_word_by_id(conn: &Connection, word_id: i64) -> SqliteResult<Option<Word>> {
    let mut stmt = conn.prepare(
        "SELECT id, word, meaning, synonyms, antonyms, COALESCE(category, 'Default') FROM vocabulary WHERE id = ?1"
    )?;
    
    let result = stmt.query_row(params![word_id], |row| {
        Ok(Word {
            id: row.get(0)?,
            word: row.get(1)?,
            meaning: row.get(2)?,
            synonyms: row.get::<_, Option<String>>(3)?.unwrap_or_default(),
            antonyms: row.get::<_, Option<String>>(4)?.unwrap_or_default(),
            category: row.get::<_, Option<String>>(5)?.unwrap_or_else(|| "Default".to_string()),
        })
    });
    
    match result {
        Ok(word) => Ok(Some(word)),
        Err(rusqlite::Error::QueryReturnedNoRows) => Ok(None),
        Err(e) => Err(e),
    }
}

/// Get all words (for MCQ option generation)
pub fn get_all_words(conn: &Connection) -> SqliteResult<Vec<Word>> {
    get_words(conn, "random", None, None)
}

/// Add a single word to the database
pub fn add_word(conn: &Connection, word: &str, meaning: &str, synonyms: &str, antonyms: &str, category: &str) -> SqliteResult<i64> {
    conn.execute(
        "INSERT INTO vocabulary (word, meaning, synonyms, antonyms, category) VALUES (?1, ?2, ?3, ?4, ?5)",
        params![word, meaning, synonyms, antonyms, category],
    )?;
    Ok(conn.last_insert_rowid())
}

/// Get all categories with word counts
pub fn get_categories(conn: &Connection) -> SqliteResult<Vec<CategoryInfo>> {
    let mut stmt = conn.prepare(
        "SELECT COALESCE(category, 'Default') as cat, COUNT(*) FROM vocabulary GROUP BY cat ORDER BY cat"
    )?;
    
    let cat_iter = stmt.query_map([], |row| {
        Ok(CategoryInfo {
            name: row.get(0)?,
            word_count: row.get(1)?,
        })
    })?;
    
    let categories: Vec<CategoryInfo> = cat_iter.filter_map(|c| c.ok()).collect();
    Ok(categories)
}

/// Delete a category and all its words
pub fn delete_category(conn: &Connection, category: &str) -> SqliteResult<usize> {
    // First delete orphan attempts
    conn.execute(
        "DELETE FROM attempts WHERE word_id IN (SELECT id FROM vocabulary WHERE category = ?1)",
        params![category],
    )?;
    
    // Then delete words
    let deleted = conn.execute(
        "DELETE FROM vocabulary WHERE category = ?1",
        params![category],
    )?;
    
    Ok(deleted)
}

// ============= Python Bindings =============

#[pyfunction]
#[pyo3(name = "init_database")]
pub fn py_init_database(db_path: &str) -> PyResult<()> {
    init_database(db_path)
        .map(|_| ())
        .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))
}

#[pyfunction]
#[pyo3(name = "get_all_words")]
pub fn py_get_all_words(db_path: &str) -> PyResult<Vec<Word>> {
    let conn = Connection::open(db_path)
        .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))?;
    get_all_words(&conn)
        .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))
}

#[pyfunction]
#[pyo3(name = "get_words_by_order")]
pub fn py_get_words_by_order(db_path: &str, order: &str, letter: Option<char>, categories: Option<Vec<String>>) -> PyResult<Vec<Word>> {
    let conn = Connection::open(db_path)
        .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))?;
    get_words(&conn, order, letter, categories)
        .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))
}

#[pyfunction]
#[pyo3(name = "get_word_by_id")]
pub fn py_get_word_by_id(db_path: &str, word_id: i64) -> PyResult<Option<Word>> {
    let conn = Connection::open(db_path)
        .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))?;
    get_word_by_id(&conn, word_id)
        .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))
}

#[pyfunction]
#[pyo3(name = "add_word")]
pub fn py_add_word(db_path: &str, word: &str, meaning: &str, synonyms: &str, antonyms: &str, category: &str) -> PyResult<i64> {
    let conn = Connection::open(db_path)
        .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))?;
    add_word(&conn, word, meaning, synonyms, antonyms, category)
        .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))
}

#[pyfunction]
#[pyo3(name = "get_categories")]
pub fn py_get_categories(db_path: &str) -> PyResult<Vec<CategoryInfo>> {
    let conn = Connection::open(db_path)
        .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))?;
    get_categories(&conn)
        .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))
}

#[pyfunction]
#[pyo3(name = "delete_category")]
pub fn py_delete_category(db_path: &str, category: &str) -> PyResult<usize> {
    let conn = Connection::open(db_path)
        .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))?;
    delete_category(&conn, category)
        .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))
}

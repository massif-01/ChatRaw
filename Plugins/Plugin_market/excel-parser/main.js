/**
 * Excel Parser Plugin for ChatRaw
 * Parses Excel files (.xlsx, .xls, .xlsm) for AI reading
 * 
 * @version 1.0.0
 * @author ChatRaw
 * @license Apache-2.0
 */
(function(ChatRaw) {
    'use strict';
    
    // Safety check
    if (!ChatRaw || !ChatRaw.hooks) {
        console.error('[ExcelParser] ChatRawPlugin not available');
        return;
    }
    
    // Get XLSX library from dependencies
    let XLSX = ChatRaw.require('xlsx');
    
    // Fallback: try window.XLSX if not found in dependencies
    if (!XLSX && typeof window !== 'undefined' && window.XLSX) {
        XLSX = window.XLSX;
    }
    
    /**
     * Format sheet data as Markdown table
     */
    function formatAsMarkdownTable(sheet, xlsxLib) {
        if (!sheet['!ref']) return '';
        
        const range = xlsxLib.utils.decode_range(sheet['!ref']);
        const rows = [];
        
        // Limits for performance
        const MAX_ROWS = 1000;
        const MAX_COLS = 50;
        const MAX_CELL_LENGTH = 100;
        
        const endRow = Math.min(range.e.r, range.s.r + MAX_ROWS);
        const endCol = Math.min(range.e.c, range.s.c + MAX_COLS);
        
        // Collect all rows
        const dataRows = [];
        for (let r = range.s.r; r <= endRow; r++) {
            const row = [];
            for (let c = range.s.c; c <= endCol; c++) {
                const cellAddress = xlsxLib.utils.encode_cell({ r: r, c: c });
                const cell = sheet[cellAddress];
                
                let value = '';
                if (cell) {
                    if (cell.w) {
                        // Use formatted value if available
                        value = cell.w;
                    } else if (cell.v !== undefined) {
                        value = String(cell.v);
                    }
                }
                
                // Clean and truncate value
                value = value.replace(/\|/g, '\\|').replace(/\n/g, ' ').trim();
                if (value.length > MAX_CELL_LENGTH) {
                    value = value.substring(0, MAX_CELL_LENGTH) + '...';
                }
                
                row.push(value);
            }
            
            // Only add non-empty rows
            if (row.some(cell => cell !== '')) {
                dataRows.push(row);
            }
        }
        
        if (dataRows.length === 0) return '';
        
        // Build Markdown table
        // First row as header
        const header = dataRows[0];
        rows.push('| ' + header.join(' | ') + ' |');
        rows.push('| ' + header.map(() => '---').join(' | ') + ' |');
        
        // Data rows
        for (let i = 1; i < dataRows.length; i++) {
            rows.push('| ' + dataRows[i].join(' | ') + ' |');
        }
        
        // Add truncation notice if needed
        if (range.e.r - range.s.r > MAX_ROWS) {
            rows.push('');
            rows.push(`*... ${range.e.r - range.s.r - MAX_ROWS} more rows truncated*`);
        }
        
        return rows.join('\n');
    }
    
    /**
     * Get sheet statistics
     */
    function getSheetStats(sheet, xlsxLib) {
        if (!sheet['!ref']) return { rows: 0, cols: 0 };
        
        const range = xlsxLib.utils.decode_range(sheet['!ref']);
        return {
            rows: range.e.r - range.s.r + 1,
            cols: range.e.c - range.s.c + 1
        };
    }
    
    /**
     * Register the parse_document hook
     */
    ChatRaw.hooks.register('parse_document', {
        fileTypes: ['.xlsx', '.xls', '.xlsm'],
        priority: 10,
        
        handler: async (file, settings) => {
            try {
                // Re-check XLSX availability
                let xlsxLib = XLSX;
                if (!xlsxLib && ChatRaw.require) {
                    xlsxLib = ChatRaw.require('xlsx');
                }
                if (!xlsxLib && typeof window !== 'undefined' && window.XLSX) {
                    xlsxLib = window.XLSX;
                }
                
                if (!xlsxLib) {
                    return {
                        success: false,
                        error: 'XLSX library not loaded. Please check your internet connection and try again.'
                    };
                }
                
                // Validate file
                if (!file || typeof file.arrayBuffer !== 'function') {
                    return {
                        success: false,
                        error: 'Invalid file object.'
                    };
                }
                
                // Read file as ArrayBuffer
                const arrayBuffer = await file.arrayBuffer();
                
                // Check file size (limit to 20MB)
                if (arrayBuffer.byteLength > 20 * 1024 * 1024) {
                    return {
                        success: false,
                        error: 'File too large. Maximum supported size is 20MB.'
                    };
                }
                
                // Parse workbook
                const workbook = xlsxLib.read(arrayBuffer, {
                    type: 'array',
                    cellDates: true,
                    cellText: true,
                    sheetRows: 1001  // Limit rows per sheet (1 extra for truncation detection)
                });
                
                if (!workbook || !workbook.SheetNames || workbook.SheetNames.length === 0) {
                    return {
                        success: false,
                        error: 'No sheets found in the Excel file.'
                    };
                }
                
                // Build output
                const contentParts = [];
                
                // File header
                contentParts.push(`**Excel File**: ${file.name || 'workbook.xlsx'}`);
                contentParts.push(`**Sheets**: ${workbook.SheetNames.length}`);
                contentParts.push('');
                
                // Process each sheet
                for (const sheetName of workbook.SheetNames) {
                    const sheet = workbook.Sheets[sheetName];
                    
                    if (!sheet || !sheet['!ref']) {
                        continue; // Skip empty sheets
                    }
                    
                    const stats = getSheetStats(sheet, xlsxLib);
                    
                    // Sheet header
                    contentParts.push(`## Sheet: ${sheetName}`);
                    contentParts.push(`*${stats.rows} rows × ${stats.cols} columns*`);
                    contentParts.push('');
                    
                    // Sheet content as Markdown table
                    const tableContent = formatAsMarkdownTable(sheet, xlsxLib);
                    if (tableContent) {
                        contentParts.push(tableContent);
                        contentParts.push('');
                    } else {
                        contentParts.push('*Empty sheet*');
                        contentParts.push('');
                    }
                }
                
                const content = contentParts.join('\n').trim();
                
                if (!content) {
                    return {
                        success: false,
                        error: 'No content found in the Excel file.'
                    };
                }
                
                return {
                    success: true,
                    content: content
                };
                
            } catch (error) {
                console.error('[ExcelParser] Error:', error);
                return {
                    success: false,
                    error: `Failed to parse Excel file: ${error.message || 'Unknown error'}`
                };
            }
        }
    });
    
    // Log successful initialization
    console.log('[ExcelParser] Plugin loaded successfully');
    
})(window.ChatRawPlugin);

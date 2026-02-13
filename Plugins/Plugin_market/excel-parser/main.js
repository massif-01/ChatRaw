/**
 * Excel Parser Pro - Enhanced Excel Parser Plugin for ChatRaw
 * Parses Excel files (.xlsx, .xls, .xlsm, .xlsb, .csv) with advanced formatting
 * 
 * Features:
 * - Formula result extraction (not formula text)
 * - Date format detection and conversion
 * - Number formatting (currency, percentage, decimals)
 * - Merged cell handling
 * - Smart empty row/column filtering
 * - Multi-sheet support with statistics
 * - Offline-ready with bundled SheetJS
 * 
 * @version 1.0.2
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
    
    // ============ Date Formatting Utilities ============
    
    /**
     * Excel date serial number to JavaScript Date
     * Excel uses 1900-01-01 as day 1 (with a bug that treats 1900 as leap year)
     */
    function excelDateToJS(serial) {
        if (typeof serial !== 'number' || isNaN(serial)) return null;
        
        // Excel's epoch is December 30, 1899
        // But there's a leap year bug (1900 was not a leap year but Excel treats it as one)
        const utcDays = Math.floor(serial - 25569);
        const utcValue = utcDays * 86400 * 1000;
        const fractionalDay = serial - Math.floor(serial);
        const msInDay = fractionalDay * 86400 * 1000;
        
        return new Date(utcValue + msInDay);
    }
    
    /**
     * Format date according to specified format
     */
    function formatDate(date, format) {
        if (!date || !(date instanceof Date) || isNaN(date.getTime())) {
            return '';
        }
        
        const year = date.getFullYear();
        const month = String(date.getMonth() + 1).padStart(2, '0');
        const day = String(date.getDate()).padStart(2, '0');
        const hours = String(date.getHours()).padStart(2, '0');
        const minutes = String(date.getMinutes()).padStart(2, '0');
        const seconds = String(date.getSeconds()).padStart(2, '0');
        
        switch (format) {
            case 'YYYY-MM-DD':
                return `${year}-${month}-${day}`;
            case 'YYYY/MM/DD':
                return `${year}/${month}/${day}`;
            case 'DD/MM/YYYY':
                return `${day}/${month}/${year}`;
            case 'MM/DD/YYYY':
                return `${month}/${day}/${year}`;
            case 'YYYY年MM月DD日':
                return `${year}年${month}月${day}日`;
            default:
                return `${year}-${month}-${day}`;
        }
    }
    
    /**
     * Check if a number format string indicates a date
     */
    function isDateFormat(fmt) {
        if (!fmt) return false;
        // Common date format patterns
        const datePatterns = [
            /y{2,4}/i,  // yy, yyyy
            /m{1,4}/i,  // m, mm, mmm, mmmm (but not when alone - could be minutes)
            /d{1,4}/i,  // d, dd, ddd, dddd
            /date/i,
            /年|月|日/,
            /\/.*\//,   // Contains two slashes like mm/dd/yy
        ];
        
        // Exclude time-only formats
        if (/^[hms:\[\]]+$/i.test(fmt)) return false;
        
        return datePatterns.some(p => p.test(fmt));
    }
    
    /**
     * Check if a number format string indicates a time (without date)
     */
    function isTimeFormat(fmt) {
        if (!fmt) return false;
        return /^[hms:\[\]\.0]+$/i.test(fmt) || /时|分|秒/.test(fmt);
    }
    
    /**
     * Format time from fractional day
     */
    function formatTime(fractionalDay) {
        const totalSeconds = Math.round(fractionalDay * 86400);
        const hours = Math.floor(totalSeconds / 3600);
        const minutes = Math.floor((totalSeconds % 3600) / 60);
        const seconds = totalSeconds % 60;
        
        return `${String(hours).padStart(2, '0')}:${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}`;
    }
    
    // ============ Number Formatting Utilities ============
    
    /**
     * Format number based on Excel number format
     */
    function formatNumber(value, format) {
        if (typeof value !== 'number' || isNaN(value)) {
            return String(value ?? '');
        }
        
        // Check for percentage format
        if (format && /%/.test(format)) {
            return (value * 100).toFixed(2) + '%';
        }
        
        // Check for currency format (¥, $, €, etc.)
        if (format) {
            const currencyMatch = format.match(/[$¥€£₹]/);
            if (currencyMatch) {
                const currency = currencyMatch[0];
                const formatted = value.toLocaleString('zh-CN', {
                    minimumFractionDigits: 2,
                    maximumFractionDigits: 2
                });
                return currency + formatted;
            }
        }
        
        // Check for thousands separator
        if (format && /#,##/.test(format)) {
            return value.toLocaleString('zh-CN');
        }
        
        // Determine decimal places from format
        if (format) {
            const decimalMatch = format.match(/\.([0#]+)/);
            if (decimalMatch) {
                const decimals = decimalMatch[1].length;
                return value.toFixed(decimals);
            }
        }
        
        // Default: reasonable precision
        if (Number.isInteger(value)) {
            return String(value);
        }
        
        // Avoid floating point display issues
        const str = value.toString();
        if (str.length > 15) {
            return value.toPrecision(10);
        }
        
        return str;
    }
    
    // ============ Cell Value Extraction ============
    
    /**
     * Get formatted cell value with proper type handling
     */
    function getCellValue(cell, xlsxLib, dateFormat) {
        if (!cell) return '';
        
        // Cell types in SheetJS:
        // b - Boolean
        // e - Error
        // n - Number
        // d - Date
        // s - String
        // z - Stub (blank)
        
        const type = cell.t;
        const value = cell.v;
        const format = cell.z; // Number format
        const formatted = cell.w; // Formatted text (if available)
        
        // Boolean
        if (type === 'b') {
            return value ? 'TRUE' : 'FALSE';
        }
        
        // Error
        if (type === 'e') {
            const errorMap = {
                0x00: '#NULL!',
                0x07: '#DIV/0!',
                0x0F: '#VALUE!',
                0x17: '#REF!',
                0x1D: '#NAME?',
                0x24: '#NUM!',
                0x2A: '#N/A',
                0x2B: '#GETTING_DATA'
            };
            return errorMap[value] || `#ERROR(${value})`;
        }
        
        // Date type (explicitly marked as date)
        if (type === 'd') {
            if (value instanceof Date) {
                return formatDate(value, dateFormat);
            }
            return formatted || String(value);
        }
        
        // Number type - check if it's actually a date
        if (type === 'n') {
            // Check if this is a date based on format
            if (isDateFormat(format)) {
                const jsDate = excelDateToJS(value);
                if (jsDate) {
                    return formatDate(jsDate, dateFormat);
                }
            }
            
            // Check if this is a time-only format
            if (isTimeFormat(format)) {
                const fractional = value - Math.floor(value);
                return formatTime(fractional);
            }
            
            // Regular number formatting
            // Prefer the pre-formatted value if it looks reasonable
            if (formatted && !/^[\d.E+-]+$/.test(formatted)) {
                return formatted;
            }
            
            return formatNumber(value, format);
        }
        
        // String type
        if (type === 's') {
            return String(value ?? '');
        }
        
        // Fallback: use formatted value or raw value
        if (formatted) {
            return formatted;
        }
        
        return String(value ?? '');
    }
    
    // ============ Merged Cells Handling ============
    
    /**
     * Build a map of merged cell regions
     */
    function buildMergeMap(sheet) {
        const mergeMap = new Map(); // "row,col" -> { startRow, startCol, endRow, endCol }
        const merges = sheet['!merges'] || [];
        
        for (const merge of merges) {
            const { s: start, e: end } = merge;
            
            // Store the merge info for the top-left cell
            const key = `${start.r},${start.c}`;
            mergeMap.set(key, {
                startRow: start.r,
                startCol: start.c,
                endRow: end.r,
                endCol: end.c,
                rowSpan: end.r - start.r + 1,
                colSpan: end.c - start.c + 1
            });
            
            // Mark all other cells in the merge as "skip"
            for (let r = start.r; r <= end.r; r++) {
                for (let c = start.c; c <= end.c; c++) {
                    if (r !== start.r || c !== start.c) {
                        mergeMap.set(`${r},${c}`, { skip: true });
                    }
                }
            }
        }
        
        return mergeMap;
    }
    
    // ============ Table Formatting ============
    
    /**
     * Format sheet data as Markdown table with enhanced features
     */
    function formatAsMarkdownTable(sheet, xlsxLib, settings) {
        if (!sheet['!ref']) return '';
        
        const range = xlsxLib.utils.decode_range(sheet['!ref']);
        const dateFormat = settings.date_format || 'YYYY-MM-DD';
        const includeEmptyRows = settings.include_empty_rows || false;
        const maxRows = settings.max_rows || 1000;
        const maxCols = settings.max_cols || 50;
        const maxCellLength = 150; // Slightly longer for better context
        
        // Build merge map
        const mergeMap = buildMergeMap(sheet);
        
        // Calculate actual data boundaries (find non-empty region)
        let dataStartRow = range.s.r;
        let dataEndRow = Math.min(range.e.r, range.s.r + maxRows - 1);
        let dataStartCol = range.s.c;
        let dataEndCol = Math.min(range.e.c, range.s.c + maxCols - 1);
        
        // Collect all rows first to analyze
        const allRows = [];
        for (let r = dataStartRow; r <= dataEndRow; r++) {
            const row = [];
            let hasContent = false;
            
            for (let c = dataStartCol; c <= dataEndCol; c++) {
                const cellAddress = xlsxLib.utils.encode_cell({ r, c });
                const cell = sheet[cellAddress];
                
                // Check merge status
                const mergeInfo = mergeMap.get(`${r},${c}`);
                if (mergeInfo?.skip) {
                    row.push(''); // Empty for merged cells (not the origin)
                    continue;
                }
                
                let value = getCellValue(cell, xlsxLib, dateFormat);
                
                // Add merge indicator if this is a merged cell origin
                if (mergeInfo && (mergeInfo.rowSpan > 1 || mergeInfo.colSpan > 1)) {
                    // Don't add indicator for now, just use the value
                    // value += ` (${mergeInfo.rowSpan}×${mergeInfo.colSpan})`;
                }
                
                // Clean value for Markdown table
                value = value
                    .replace(/\|/g, '\\|')
                    .replace(/\n/g, ' ')
                    .replace(/\r/g, '')
                    .trim();
                
                // Truncate if too long
                if (value.length > maxCellLength) {
                    value = value.substring(0, maxCellLength) + '...';
                }
                
                if (value !== '') {
                    hasContent = true;
                }
                
                row.push(value);
            }
            
            // Only add non-empty rows (unless includeEmptyRows is true)
            if (hasContent || includeEmptyRows) {
                allRows.push(row);
            }
        }
        
        if (allRows.length === 0) return '';
        
        // Remove empty columns from the end
        let lastNonEmptyCol = 0;
        for (const row of allRows) {
            for (let c = row.length - 1; c >= 0; c--) {
                if (row[c] !== '') {
                    lastNonEmptyCol = Math.max(lastNonEmptyCol, c);
                    break;
                }
            }
        }
        
        // Trim rows to actual content width
        const trimmedRows = allRows.map(row => row.slice(0, lastNonEmptyCol + 1));
        
        if (trimmedRows.length === 0 || trimmedRows[0].length === 0) return '';
        
        // Build Markdown table
        const output = [];
        
        // Header row (first row)
        const header = trimmedRows[0];
        
        // Generate column headers (use letters if first row looks like data)
        const looksLikeHeader = header.some(h => 
            typeof h === 'string' && h.length > 0 && !/^[\d.,¥$€£%+-]+$/.test(h)
        );
        
        if (looksLikeHeader) {
            // Use first row as header
            output.push('| ' + header.map(h => h || ' ').join(' | ') + ' |');
            output.push('| ' + header.map(() => '---').join(' | ') + ' |');
            
            // Data rows
            for (let i = 1; i < trimmedRows.length; i++) {
                const row = trimmedRows[i];
                // Pad row if shorter than header
                while (row.length < header.length) {
                    row.push('');
                }
                output.push('| ' + row.join(' | ') + ' |');
            }
        } else {
            // Generate A, B, C... headers
            const colHeaders = header.map((_, i) => {
                let col = '';
                let n = i;
                do {
                    col = String.fromCharCode(65 + (n % 26)) + col;
                    n = Math.floor(n / 26) - 1;
                } while (n >= 0);
                return col;
            });
            
            output.push('| ' + colHeaders.join(' | ') + ' |');
            output.push('| ' + colHeaders.map(() => '---').join(' | ') + ' |');
            
            // All rows as data
            for (const row of trimmedRows) {
                while (row.length < colHeaders.length) {
                    row.push('');
                }
                output.push('| ' + row.join(' | ') + ' |');
            }
        }
        
        // Add truncation notice if needed
        const totalRows = range.e.r - range.s.r + 1;
        const totalCols = range.e.c - range.s.c + 1;
        
        if (totalRows > maxRows) {
            output.push('');
            output.push(`*... 还有 ${totalRows - maxRows} 行数据未显示*`);
        }
        
        if (totalCols > maxCols) {
            output.push(`*... 还有 ${totalCols - maxCols} 列数据未显示*`);
        }
        
        return output.join('\n');
    }
    
    /**
     * Get sheet statistics
     */
    function getSheetStats(sheet, xlsxLib) {
        if (!sheet['!ref']) return { rows: 0, cols: 0, merges: 0 };
        
        const range = xlsxLib.utils.decode_range(sheet['!ref']);
        const merges = sheet['!merges'] || [];
        
        return {
            rows: range.e.r - range.s.r + 1,
            cols: range.e.c - range.s.c + 1,
            merges: merges.length
        };
    }
    
    /**
     * Detect if sheet contains specific data patterns
     */
    function analyzeSheetContent(sheet, xlsxLib) {
        const analysis = {
            hasFormulas: false,
            hasDates: false,
            hasNumbers: false,
            hasCurrency: false,
            hasPercentage: false
        };
        
        if (!sheet['!ref']) return analysis;
        
        const range = xlsxLib.utils.decode_range(sheet['!ref']);
        const sampleSize = Math.min(100, (range.e.r - range.s.r + 1) * (range.e.c - range.s.c + 1));
        let checked = 0;
        
        for (let r = range.s.r; r <= range.e.r && checked < sampleSize; r++) {
            for (let c = range.s.c; c <= range.e.c && checked < sampleSize; c++) {
                const addr = xlsxLib.utils.encode_cell({ r, c });
                const cell = sheet[addr];
                
                if (!cell) continue;
                checked++;
                
                if (cell.f) analysis.hasFormulas = true;
                if (cell.t === 'd' || (cell.t === 'n' && isDateFormat(cell.z))) analysis.hasDates = true;
                if (cell.t === 'n') analysis.hasNumbers = true;
                if (cell.z && /[$¥€£]/.test(cell.z)) analysis.hasCurrency = true;
                if (cell.z && /%/.test(cell.z)) analysis.hasPercentage = true;
            }
        }
        
        return analysis;
    }
    
    // ============ Main Handler ============
    
    /**
     * Register the parse_document hook
     */
    ChatRaw.hooks.register('parse_document', {
        fileTypes: ['.xlsx', '.xls', '.xlsm', '.xlsb', '.csv'],
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
                        error: 'XLSX library not loaded. Please reinstall the Excel Parser plugin.'
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
                
                // Parse workbook with full options
                const workbook = xlsxLib.read(arrayBuffer, {
                    type: 'array',
                    cellDates: true,      // Parse dates as Date objects
                    cellFormula: false,   // Don't need formula text, just results
                    cellText: true,       // Get formatted text
                    cellStyles: false,    // Don't need styles
                    sheetRows: (settings.max_rows || 1000) + 1,  // +1 for header detection
                    WTF: false            // Don't throw on unexpected features
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
                const filename = file.name || 'workbook.xlsx';
                const ext = filename.split('.').pop()?.toLowerCase() || 'xlsx';
                const fileTypeNames = {
                    'xlsx': 'Excel Workbook',
                    'xls': 'Excel 97-2003',
                    'xlsm': 'Excel Macro-Enabled',
                    'xlsb': 'Excel Binary',
                    'csv': 'CSV Text'
                };
                
                contentParts.push(`**文件名**: ${filename}`);
                contentParts.push(`**文件类型**: ${fileTypeNames[ext] || 'Excel'}`);
                contentParts.push(`**工作表数量**: ${workbook.SheetNames.length}`);
                contentParts.push('');
                
                // Process each sheet
                let totalDataRows = 0;
                
                for (const sheetName of workbook.SheetNames) {
                    const sheet = workbook.Sheets[sheetName];
                    
                    if (!sheet || !sheet['!ref']) {
                        contentParts.push(`## 工作表: ${sheetName}`);
                        contentParts.push('*空工作表*');
                        contentParts.push('');
                        continue;
                    }
                    
                    const stats = getSheetStats(sheet, xlsxLib);
                    const analysis = analyzeSheetContent(sheet, xlsxLib);
                    
                    // Sheet header
                    contentParts.push(`## 工作表: ${sheetName}`);
                    contentParts.push(`**数据范围**: ${stats.rows} 行 × ${stats.cols} 列`);
                    
                    // Add content type indicators
                    const contentTypes = [];
                    if (analysis.hasFormulas) contentTypes.push('公式');
                    if (analysis.hasDates) contentTypes.push('日期');
                    if (analysis.hasCurrency) contentTypes.push('货币');
                    if (analysis.hasPercentage) contentTypes.push('百分比');
                    if (stats.merges > 0) contentTypes.push(`${stats.merges}处合并`);
                    
                    if (contentTypes.length > 0) {
                        contentParts.push(`**内容特征**: ${contentTypes.join('、')}`);
                    }
                    
                    contentParts.push('');
                    
                    // Sheet content as Markdown table
                    const tableContent = formatAsMarkdownTable(sheet, xlsxLib, settings);
                    if (tableContent) {
                        contentParts.push(tableContent);
                        contentParts.push('');
                        totalDataRows += stats.rows;
                    } else {
                        contentParts.push('*无有效数据*');
                        contentParts.push('');
                    }
                }
                
                // Summary
                if (workbook.SheetNames.length > 1) {
                    contentParts.push('---');
                    contentParts.push(`**总计**: ${workbook.SheetNames.length} 个工作表，约 ${totalDataRows} 行数据`);
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
    console.log('[ExcelParser Pro] Plugin loaded successfully (v1.0.2)');
    
})(window.ChatRawPlugin);

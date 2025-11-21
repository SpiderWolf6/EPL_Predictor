import time
import pandas as pd
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    NoSuchElementException,
    ElementClickInterceptedException,
    TimeoutException,
)


# --- CONFIG BLOCK ---
SOFASCORE_CONFIG = {
    "home_url": "https://www.sofascore.com",
    "premier_league_url": "https://www.sofascore.com/tournament/football/england/premier-league/17",
    "valid_stat_types": [
        "General", "Attack", "Defense", 
        "Goalkeeping", "Passing", "Detailed"
    ],
    "season_map": {
        "2024/25": "61627",
        "2023/24": "52760",
        "2022/23": "41886",
        "2021/22": "37036",
        "2020/21": "29415",
    },
    "wait_timeout": 30,
    "scroll_delay": 1.5,
    "click_delay": 0.5,
    "page_load_delay": 3,
    "manual_wait_time": 30,
}


def scrape_sofascore(year: str, stat_type: str) -> pd.DataFrame:
    """
    Scrape SofaScore Premier League player statistics.
    
    Input:
        year: "2023/24" format
        stat_type: e.g. "Attack", "Defense", "Passing", "General", "Goalkeeping", "Detailed"
    
    Output:
        Clean pandas DataFrame containing the full stats table
    """
    
    # --- Input Validation ---
    # Normalize stat_type (handle variations)
    stat_type_normalized = stat_type.capitalize()
    # Handle common variations
    if stat_type_normalized in ["Attacking"]:
        stat_type_normalized = "Attack"
    if stat_type_normalized in ["Defending"]:
        stat_type_normalized = "Defense"
    
    if stat_type_normalized not in SOFASCORE_CONFIG["valid_stat_types"]:
        raise ValueError(
            f"Invalid stat_type: '{stat_type}'. "
            f"Valid options: {', '.join(SOFASCORE_CONFIG['valid_stat_types'])}"
        )
    
    # Validate year format
    if not (len(year) == 7 and year[4] == "/" and year[:4].isdigit() and year[5:].isdigit()):
        raise ValueError(
            f"Invalid year format: '{year}'. Expected format: 'YYYY/YY' (e.g., '2023/24')"
        )
    
    # Check if season is supported
    season_id = SOFASCORE_CONFIG["season_map"].get(year)
    if not season_id:
        raise ValueError(
            f"Season '{year}' not supported. "
            f"Supported seasons: {', '.join(SOFASCORE_CONFIG['season_map'].keys())}"
        )
    
    print(f"Scraping SofaScore: {year} - {stat_type_normalized}")
    
    # --- Setup Browser ---
    options = webdriver.ChromeOptions()
    options.add_argument("--start-maximized")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--no-sandbox")
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    options.add_experimental_option('excludeSwitches', ['enable-logging', 'enable-automation'])
    options.add_experimental_option("useAutomationExtension", False)
    
    driver = webdriver.Chrome(options=options)
    
    # Remove webdriver property to avoid detection
    driver.execute_cdp_cmd('Network.setUserAgentOverride', {
        "userAgent": 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    })
    driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
    
    # --- Navigate to Home Page First ---
    print(f"Step 1: Navigating to SofaScore home page...")
    print(f"URL: {SOFASCORE_CONFIG['home_url']}")
    
    try:
        driver.get(SOFASCORE_CONFIG["home_url"])
    except Exception as e:
        print(f"Error loading home page: {e}")
        driver.set_page_load_timeout(60)
        try:
            driver.get(SOFASCORE_CONFIG["home_url"])
        except Exception as e2:
            driver.quit()
            raise ConnectionError(f"Could not load SofaScore home page. Error: {e2}")
    
    # Wait for home page to load
    wait = WebDriverWait(driver, SOFASCORE_CONFIG["wait_timeout"])
    time.sleep(3)
    
    # --- Navigate to Premier League ---
    print(f"Step 2: Navigating to Premier League page...")
    print(f"URL: {SOFASCORE_CONFIG['premier_league_url']}")
    
    try:
        driver.get(SOFASCORE_CONFIG["premier_league_url"])
    except Exception as e:
        print(f"Error loading Premier League page: {e}")
        driver.set_page_load_timeout(60)
        try:
            driver.get(SOFASCORE_CONFIG["premier_league_url"])
        except Exception as e2:
            driver.quit()
            raise ConnectionError(f"Could not load Premier League page. Error: {e2}")
    
    # Wait for Premier League page to load
    time.sleep(5)
    
    try:
        wait.until(EC.presence_of_element_located((By.TAG_NAME, "body")))
    except TimeoutException:
        print("Warning: Page load timeout, continuing anyway...")
    
    # --- Navigate to Statistics (try clicking Statistics link/button) ---
    print("Step 3: Looking for Statistics link/button...")
    time.sleep(3)
    
    stats_clicked = False
    try:
        # Try to find and click "Statistics" link/button
        stats_selectors = [
            "//a[contains(text(), 'Statistics')]",
            "//a[contains(@href, 'statistics')]",
            "//button[contains(text(), 'Statistics')]",
            "//div[contains(text(), 'Statistics')]",
            "//span[contains(text(), 'Statistics')]",
        ]
        
        for selector in stats_selectors:
            try:
                stats_elem = driver.find_element(By.XPATH, selector)
                driver.execute_script(
                    "arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", 
                    stats_elem
                )
                time.sleep(1)
                driver.execute_script("arguments[0].click();", stats_elem)
                stats_clicked = True
                print("Clicked Statistics link")
                time.sleep(5)
                break
            except NoSuchElementException:
                continue
    except Exception as e:
        print(f"Warning: Could not click Statistics link: {e}")
    
    # If clicking didn't work, try direct URL
    if not stats_clicked:
        print("Step 3 (alternative): Navigating directly to statistics page...")
        stats_url = f"{SOFASCORE_CONFIG['premier_league_url']}/season/{season_id}/statistics"
        print(f"URL: {stats_url}")
        
        try:
            driver.get(stats_url)
            time.sleep(5)
        except Exception as e:
            print(f"Error loading statistics page: {e}")
            # Try without season ID
            stats_url_alt = f"{SOFASCORE_CONFIG['premier_league_url']}/statistics"
            print(f"Trying alternative URL: {stats_url_alt}")
            try:
                driver.get(stats_url_alt)
                time.sleep(5)
            except Exception as e2:
                print(f"Both statistics URLs failed. Continuing anyway...")
    
    # Wait for statistics page to load
    time.sleep(3)
    
    # --- Select Stat Type ---
    print(f"Looking for stat type button: {stat_type_normalized}")
    time.sleep(3)
    
    try:
        # Find stat type buttons/tabs
        stat_buttons = driver.find_elements(By.CSS_SELECTOR, "button, a[role='tab'], div[role='button']")
        found = False
        
        for button in stat_buttons:
            button_text = button.text.strip()
            if (stat_type_normalized.lower() in button_text.lower() or 
                button_text.lower() in stat_type_normalized.lower() or
                (stat_type_normalized == "Defense" and "defense" in button_text.lower()) or
                (stat_type_normalized == "Attack" and "attack" in button_text.lower())):
                
                print(f"Found button: '{button_text}'")
                driver.execute_script(
                    "arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", 
                    button
                )
                time.sleep(SOFASCORE_CONFIG["scroll_delay"])
                
                # Try JavaScript click first (more reliable)
                try:
                    driver.execute_script("arguments[0].click();", button)
                    found = True
                    print(f"Clicked '{stat_type_normalized}' tab")
                    time.sleep(4)
                    break
                except Exception:
                    try:
                        button.click()
                        found = True
                        print(f"Clicked '{stat_type_normalized}' tab")
                        time.sleep(4)
                        break
                    except ElementClickInterceptedException:
                        # Try scrolling more and clicking again
                        driver.execute_script("window.scrollTo(0, arguments[0].offsetTop - 100);", button)
                        time.sleep(1)
                        driver.execute_script("arguments[0].click();", button)
                        found = True
                        print(f"Clicked '{stat_type_normalized}' tab (after scroll)")
                        time.sleep(4)
                        break
        
        if not found:
            print(f"Warning: Could not find exact match for '{stat_type_normalized}', may already be selected")
    except Exception as e:
        print(f"Warning: Error selecting stat type: {e}")
    
    # --- Wait for Manual Adjustments (matching Understat pattern) ---
    print(f"\nWaiting {SOFASCORE_CONFIG['manual_wait_time']} seconds for manual changes...")
    time.sleep(SOFASCORE_CONFIG["manual_wait_time"])
    print("Starting extraction...")
    
    wait = WebDriverWait(driver, SOFASCORE_CONFIG["wait_timeout"])
    
    # --- Helper: convert table HTML → DataFrame ---
    def table_to_df(container_element):
        """Parse table in a container into DataFrame."""
        try:
            table = container_element.find_element(By.TAG_NAME, "table")
        except NoSuchElementException:
            table = container_element  # Fallback
        
        rows = table.find_elements(By.TAG_NAME, "tr")
        data = []
        header_row = None
        
        for row in rows:
            # Try header first, else normal cells
            cells = row.find_elements(By.TAG_NAME, "th")
            if not cells:
                cells = row.find_elements(By.TAG_NAME, "td")
            
            cell_texts = [c.text.strip() for c in cells]
            
            # Skip empty rows
            if not any(cell_texts):
                continue
            
            # First non-empty row is likely the header
            if header_row is None and cell_texts:
                header_row = cell_texts
            else:
                data.append(cell_texts)
        
        # Skip empty or invalid tables
        if not header_row or len(data) < 1:
            return pd.DataFrame()
        
        # Ensure all rows have same length as header
        max_cols = len(header_row)
        data_cleaned = []
        for row in data:
            if len(row) == max_cols:
                data_cleaned.append(row)
            elif len(row) < max_cols:
                # Pad short rows
                data_cleaned.append(row + [''] * (max_cols - len(row)))
            else:
                # Truncate long rows
                data_cleaned.append(row[:max_cols])
        
        # Create DataFrame with first row as headers
        df = pd.DataFrame(data_cleaned, columns=header_row)
        return df
    
    # --- 1️⃣ STATISTICS TABLE ---
    print(f"Extracting {stat_type_normalized} statistics table...")
    
    stats_table = pd.DataFrame()
    
    # Wait for table to load after clicking stat type
    print("Waiting for table to load...")
    try:
        # Wait for any table to appear
        wait.until(EC.presence_of_element_located((By.TAG_NAME, "table")))
        print("Table element found")
    except TimeoutException:
        print("No table tag found, will try alternative methods...")
    
    time.sleep(5)  # Extra wait for dynamic content
    
    try:
        # Try multiple strategies to find the table
        all_tables = driver.find_elements(By.TAG_NAME, "table")
        print(f"Found {len(all_tables)} table(s) on page")
        
        if len(all_tables) == 0:
            print("No tables found. Trying alternative selectors...")
            # Try finding by common SofaScore table containers
            table_containers = driver.find_elements(By.CSS_SELECTOR, "[class*='table'], [class*='Table'], [class*='stats'], [class*='Stats']")
            print(f"Found {len(table_containers)} potential table containers")
        
        for idx, table in enumerate(all_tables):
            rows = table.find_elements(By.TAG_NAME, "tr")
            print(f"Table {idx + 1}: {len(rows)} rows")
            
            if len(rows) > 2:  # At least header + 1 data row
                # Check if this looks like a stats table
                first_row_text = rows[0].text.lower() if rows else ""
                print(f"  First row text: {first_row_text[:100]}...")  # First 100 chars
                
                # More lenient check - just needs to have multiple rows
                if len(rows) > 5 or any(k in first_row_text for k in ['player', 'team', 'name', 'position', 'goals', 'assists', 'tackles', 'passes', 'saves', 'clean', 'rank', 'rating']):
                    # Scroll to view
                    driver.execute_script(
                        "arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", 
                        table
                    )
                    time.sleep(SOFASCORE_CONFIG["scroll_delay"])
                    
                    potential_df = table_to_df(table)
                    print(f"  Extracted DataFrame: {potential_df.shape}")
                    
                    if not potential_df.empty and len(potential_df.columns) > 2:
                        stats_table = potential_df
                        print(f"Found stats table with {stats_table.shape[0]} players")
                        break
        
        if stats_table.empty:
            # Try scrolling down to load more content
            print("Scrolling page to load more content...")
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(2)
            driver.execute_script("window.scrollTo(0, 0);")
            time.sleep(2)
            
            # Try again with tables
            all_tables = driver.find_elements(By.TAG_NAME, "table")
            print(f"After scroll: Found {len(all_tables)} table(s)")
            
            for table in all_tables:
                rows = table.find_elements(By.TAG_NAME, "tr")
                if len(rows) > 5:
                    potential_df = table_to_df(table)
                    if not potential_df.empty and len(potential_df.columns) > 2:
                        stats_table = potential_df
                        print(f"Found stats table after scroll: {stats_table.shape[0]} players")
                        break
            
            # If still empty, try extracting from div-based table structure
            if stats_table.empty:
                print("Trying to extract from div-based table structure...")
                try:
                    # Look for common SofaScore table patterns
                    table_rows = driver.find_elements(By.CSS_SELECTOR, "[class*='row'], [class*='Row'], [class*='player'], [class*='Player']")
                    print(f"Found {len(table_rows)} potential row elements")
                    
                    if len(table_rows) > 10:
                        # Try to extract data from these elements
                        data_rows = []
                        for row in table_rows[:100]:  # Limit to first 100
                            text = row.text.strip()
                            if text and len(text.split('\n')) >= 3:
                                parts = [p.strip() for p in text.split('\n') if p.strip()]
                                if len(parts) >= 3:
                                    data_rows.append(parts)
                        
                        if len(data_rows) > 5:
                            # Use first row as header if it looks like headers
                            if any(k in data_rows[0][0].lower() for k in ['rank', 'player', 'team', 'name']):
                                header = data_rows[0]
                                data = data_rows[1:]
                            else:
                                # Create generic headers
                                header = [f"Column_{i+1}" for i in range(len(data_rows[0]))]
                                data = data_rows
                            
                            # Normalize row lengths
                            max_cols = len(header)
                            data_cleaned = []
                            for row in data:
                                if len(row) == max_cols:
                                    data_cleaned.append(row)
                                elif len(row) < max_cols:
                                    data_cleaned.append(row + [''] * (max_cols - len(row)))
                                else:
                                    data_cleaned.append(row[:max_cols])
                            
                            stats_table = pd.DataFrame(data_cleaned, columns=header)
                            print(f"Extracted from div structure: {stats_table.shape[0]} rows")
                except Exception as e:
                    print(f"Error extracting from div structure: {e}")
            
            if stats_table.empty:
                stats_table = pd.DataFrame()
    except Exception as e:
        print(f"Error during table extraction: {e}")
        stats_table = pd.DataFrame()
    
    if stats_table.empty:
        print("WARNING: Could not find statistics table.")
        print("   Please verify the stat_type and year are correct.")
        print("   Returning empty DataFrame.")
        driver.quit()
        return pd.DataFrame()
    
    print(f"Statistics table: {stats_table.shape[0]} rows")
    
    # --- 2️⃣ PAGINATION (if present) ---
    print("Checking for pagination...")
    
    all_page_dfs = [stats_table] if not stats_table.empty else []
    
    # --- Extract one page ---
    def extract_current_page():
        """Grab table from current page."""
        try:
            all_tables = driver.find_elements(By.TAG_NAME, "table")
            for table in all_tables:
                rows = table.find_elements(By.TAG_NAME, "tr")
                if len(rows) > 5:
                    df = table_to_df(table)
                    if not df.empty and len(df.columns) > 3:
                        return df
        except Exception:
            pass
        return pd.DataFrame()
    
    # Look for "Next" or pagination buttons
    next_button_selectors = [
        "button[aria-label*='Next']",
        "button[aria-label*='next']",
        "a[aria-label*='Next']",
        "a[aria-label*='next']",
        "//button[contains(text(), 'Next')]",
        "//a[contains(text(), 'Next')]",
        "//button[@class*='next']",
        "//a[@class*='next']",
    ]
    
    page_count = 0
    max_pages = 50  # Safety limit
    
    # --- Loop through all pages ---
    while page_count < max_pages:
        next_button = None
        
        # Try to find next button
        for selector in next_button_selectors:
            try:
                if selector.startswith("//"):
                    next_button = driver.find_element(By.XPATH, selector)
                else:
                    next_button = driver.find_element(By.CSS_SELECTOR, selector)
                
                # Check if button is disabled
                try:
                    disabled = driver.execute_script("return arguments[0].disabled;", next_button)
                    if disabled:
                        next_button = None
                        break
                except Exception:
                    pass
                
                # Check if button is visible and clickable
                if next_button and next_button.is_displayed():
                    break
                else:
                    next_button = None
            except NoSuchElementException:
                continue
        
        if not next_button:
            break
        
        # Click next button
        try:
            driver.execute_script(
                "arguments[0].scrollIntoView({block: 'center'});", 
                next_button
            )
            time.sleep(SOFASCORE_CONFIG["click_delay"])
            
            try:
                next_button.click()
            except ElementClickInterceptedException:
                driver.execute_script("arguments[0].click();", next_button)
            
            # Wait for new page to load
            time.sleep(SOFASCORE_CONFIG["page_load_delay"])
            
            # Extract current page
            page_df = extract_current_page()
            if not page_df.empty:
                all_page_dfs.append(page_df)
                page_count += 1
                print(f"  Extracted page {page_count + 1}")
            else:
                break
        except (NoSuchElementException, TimeoutException, Exception):
            break
    
    # Combine all pages
    if len(all_page_dfs) > 1:
        print(f"Extracted {len(all_page_dfs)} pages total")
    elif len(all_page_dfs) == 1:
        print("Single page (no pagination)")
    
    # --- 3️⃣ COMBINE & CLEAN DATA ---
    print("Combining and cleaning data...")
    
    if len(all_page_dfs) > 1:
        # Combine all pages
        final_df = pd.concat(all_page_dfs, ignore_index=True)
        # Remove duplicates (in case of overlap)
        final_df = final_df.drop_duplicates().reset_index(drop=True)
    elif len(all_page_dfs) == 1:
        final_df = all_page_dfs[0].copy()
    else:
        final_df = pd.DataFrame()
    
    if not final_df.empty:
        # Clean column names
        final_df.columns = [col.strip() for col in final_df.columns]
        
        # Convert numeric columns
        for col in final_df.columns:
            if col.lower() not in ['player', 'team', 'name', 'position', 'nationality', 'country']:
                try:
                    # Remove any non-numeric characters except decimal points and minus signs
                    final_df[col] = pd.to_numeric(
                        final_df[col].astype(str).str.replace(r'[^\d\.\-]', '', regex=True),
                        errors='coerce'
                    )
                except Exception:
                    pass  # Keep as string if conversion fails
    
    print(f"Final table: {final_df.shape[0]} rows, {final_df.shape[1]} columns")
    
    # --- Close Browser ---
    driver.quit()
    print("Extraction complete!\n")
    
    return final_df


# --- Test Example ---
if __name__ == "__main__":
    # Example 1: Attack stats
    print("Example 1: Attack stats for 2023/24 season")
    print("-" * 60)
    df = scrape_sofascore("2023/24", "Attack")
    
    if not df.empty:
        print(df.head(10))
        print(f"\nShape: {df.shape}")
        df.to_csv("sofascore_attacking_2023_24.csv", index=False)
        print("Saved to: sofascore_attacking_2023_24.csv")
    else:
        print("No data extracted.")
    
    print("\n" + "="*60 + "\n")

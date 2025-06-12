from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import Select
from selenium.common.exceptions import NoSuchElementException
import time
import json
import re

# 設置 Selenium WebDriver
chrome_options = Options()
chrome_options.add_argument("--headless")  # 不顯示瀏覽器界面
service = Service('chromedriver.exe')  # 這裡替換成你的 chromedriver 路徑
driver = webdriver.Chrome(service=service, options=chrome_options)

# 訪問頁面
url = "https://store.steampowered.com/curator/44716606-Taiwanese-Games"
driver.get(url)

# 等待頁面加載完成
time.sleep(2)

# 滾動頁面並加載更多遊戲
games_data = []
previous_height = driver.execute_script("return document.body.scrollHeight")

while True:
    # 找到所有遊戲項目
    game_cells = driver.find_elements(By.CSS_SELECTOR, 'div[data-panel][role="button"].recommendation')
    
    # 如果已經抓取過的遊戲數量比上次多，就保存新抓取的遊戲
    if len(games_data) < len(game_cells):
        for game in game_cells[len(games_data):]:
            # 取得遊戲名稱
            try:
                game_name = game.find_element(By.CSS_SELECTOR, 'div.capsule img').get_attribute('alt')
            except Exception as e:
                game_name = "Unknown Game"
            
            # 取得遊戲圖片
            try:
                game_image = game.find_element(By.CSS_SELECTOR, 'div.capsule img').get_attribute('src')
            except Exception as e:
                game_image = "Unknown Image"
            
            # 取得遊戲連結
            try:
                game_link = game.find_element(By.TAG_NAME, 'a').get_attribute('href')
            except Exception as e:
                game_link = "Unknown Link"
            
            # 取得開發者資訊
            try:
                developer_info = game.find_element(By.CSS_SELECTOR, '.recommendation_desc').text.strip()
                if 'Developer:' in developer_info:
                    developer = developer_info.split('Developer:')[1].split('Year:')[0].strip()
                else:
                    developer = "Unknown Developer"
            except Exception as e:
                developer = "Unknown Developer"
            
            # 初始化變數
            original_price = "Unknown Price"
            release_date = "Unknown Date"
            tags = []
            
            # 如果遊戲連結有效，進入遊戲頁面抓取更多資訊
            if game_link != "Unknown Link":
                try:
                    # 在新標籤頁中打開遊戲頁面
                    driver.execute_script("window.open('');")
                    driver.switch_to.window(driver.window_handles[1])
                    driver.get(game_link)
                    
                    # 等待頁面加載
                    time.sleep(3)

                    # 檢查是否有年齡驗證
                    try:
                        age_gate = driver.find_element(By.ID, 'agegate')
                        if age_gate:
                            # 使用 Select 選擇器來選擇年、月、日
                            Select(driver.find_element(By.ID, 'ageYear')).select_by_value('2002')
                            Select(driver.find_element(By.ID, 'ageMonth')).select_by_value('10')
                            Select(driver.find_element(By.ID, 'ageDay')).select_by_value('9')
                            
                            # 點擊確認進入
                            driver.find_element(By.CSS_SELECTOR, 'a.btnv6_blue_hoverfade.btn_medium').click()
                            time.sleep(3)
                    except NoSuchElementException:
                        pass
                    
                    # 抓取發行日期
                    try:
                        release_date = driver.find_element(By.CSS_SELECTOR, '.date').text.strip()
                    except Exception as e:
                        pass
                    
                    # 抓取原價
                    try:
                        # 先檢查是否有折扣價格
                        discount_block = driver.find_element(By.CSS_SELECTOR, '.discount_block.game_purchase_discount')
                        if discount_block:
                            original_price = driver.find_element(By.CSS_SELECTOR, '.discount_original_price').text.strip()
                    except NoSuchElementException:
                        try:
                            # 如果沒有折扣，直接抓取價格
                            original_price = driver.find_element(By.CSS_SELECTOR, '.game_purchase_price.price').text.strip()
                        except NoSuchElementException:
                            if release_date == "待公告" or "即將推出":
                                original_price = "待公告"
                            else:
                                original_price = "Unknown Price"
                    
                    # 抓取標籤
                    try:
                        tag_elements = driver.find_elements(By.CSS_SELECTOR, 'a.app_tag')
                        tags = [tag.text.strip() for tag in tag_elements if tag.text.strip()]
                    except Exception as e:
                        tags = []
                    
                    # 關閉當前標籤頁並返回原始頁面
                    driver.close()
                    driver.switch_to.window(driver.window_handles[0])
                    time.sleep(1)
                    
                except Exception as e:
                    print(f"Error processing game page {game_name}: {str(e)}")
                    # 確保返回原始頁面
                    if len(driver.window_handles) > 1:
                        driver.close()
                        driver.switch_to.window(driver.window_handles[0])
            
            # 儲存資料
            games_data.append({
                "game_name": game_name,
                "link": game_link,
                "game_image": game_image,
                "developer": developer,
                "release_date": release_date,
                "original_price": original_price,
                "tags": tags,
            })

    # 滾動頁面
    driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
    
    # 等待頁面加載更多
    time.sleep(2)
    
    # 檢查頁面是否滾動到底部，如果滾動到底則停止
    new_height = driver.execute_script("return document.body.scrollHeight")
    if new_height == previous_height:
        break
    previous_height = new_height

# 儲存為 JSON 文件
with open("all_games.json", "w", encoding="utf-8") as f:
    json.dump(games_data, f, ensure_ascii=False, indent=4)
    
print(f"抓取成功，共找到 {len(games_data)} 款遊戲。已儲存至 all_games.json")

# 關閉瀏覽器
driver.quit()
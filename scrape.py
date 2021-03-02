import time
import pickle
import logging
from typing import Optional
from dataclasses import dataclass
from timeit import default_timer as timer

from selenium import webdriver
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.common.by import By
from selenium.common.exceptions import StaleElementReferenceException
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support.expected_conditions import presence_of_element_located, element_to_be_clickable

BASE_URL = "https://niftygateway.com/itemdetail/secondary/0x2250d7c238392f4b575bb26c672afe45f0adcb75/12100010061"

logging.basicConfig(level=logging.INFO)


@dataclass
class Profile:
    name: str
    username: str
    link: str
    num_pieces: Optional[int] = None


def setup():
    options = Options()
    options.headless = True

    driver = webdriver.Firefox(options=options)
    wait = WebDriverWait(driver, 10)
    return driver, wait


def click_global_history(driver, wait, timeout=10):
    class_name = "MuiTab-wrapper"
    button_text = "GLOBAL HISTORY"
    t_start = timer()
    glob_hist_button = None
    while True:
        try:
            wait.until(element_to_be_clickable((By.CLASS_NAME, class_name)))
            for e in driver.find_elements_by_class_name(class_name):
                if e.text.strip() == button_text:
                    glob_hist_button = e
                    break
        except StaleElementReferenceException:
            pass
        if glob_hist_button is not None:
            break
        t_current = timer()
        if t_current - t_start > timeout:
            raise TimeoutError(f"Could not find button {button_text}")
        time.sleep(0.2)
    glob_hist_button.click()


def get_profiles_on_current_page(driver, wait, timeout=10):
    t_start = timer()
    while True:
        try:
            profiles = try_get_profiles(driver=driver, wait=wait)
        except StaleElementReferenceException:
            profiles = {}
        if len(profiles) > 0:
            break
        t_current = timer()
        if t_current - t_start > timeout:
            raise TimeoutError("Could not find list of profiles")
        time.sleep(0.2)
    return profiles


def try_get_profiles(driver, wait):
    profiles = {}
    for e in driver.find_elements_by_tag_name("li"):
        if not e.is_displayed():
            continue
        links = e.find_elements_by_tag_name('a')
        for link_elem in links:
            link = link_elem.get_attribute('href')
            logging.info(f'Found link {link}')
            texts = link_elem.find_elements_by_tag_name('p')
            assert len(texts) == 1
            name = texts[0].text
            username = _username_from_link(link=link)
            profile = Profile(name=name, username=username, link=link)
            profiles[link] = profile
    return profiles


def _username_from_link(link):
    return link.split('/')[-1].strip()


def click_next_page(driver, wait):
    tag_name = "nav"
    wait.until(presence_of_element_located((By.TAG_NAME, tag_name)))
    navs = [e for e in driver.find_elements_by_tag_name(tag_name) if e.is_displayed()]
    next_page_buttons = [
        b
        for nav in navs
        for b in nav.find_elements_by_tag_name('button')
        if b.get_attribute('aria-label') == "Go to next page"
    ]
    assert len(next_page_buttons) == 1
    next_page_button = next_page_buttons[0]
    if next_page_button.get_attribute('disabled') == 'true':
        return False
    else:
        next_page_button.click()
        return True


def get_all_profiles(driver, wait):
    driver.get(BASE_URL)

    profiles = {}
    click_global_history(driver=driver, wait=wait)
    got_new_page = True
    while got_new_page:
        profiles.update(get_profiles_on_current_page(driver=driver, wait=wait))
        got_new_page = click_next_page(driver=driver, wait=wait)

    return profiles


def get_num_pieces(driver, wait, profile: Profile, timeout=10):
    driver.get(profile.link)
    class_name = "MuiTab-wrapper"
    t_start = timer()
    while True:
        wait.until(presence_of_element_located((By.CLASS_NAME, class_name)))
        elems = driver.find_elements_by_class_name(class_name)
        assert len(elems) == 1
        nifties_text = elems[0].text
        assert nifties_text.startswith("Nifties (")
        num_pieces = nifties_text[len("Nifties ("):-1]
        if num_pieces == '--':
            continue
        try:
            num_pieces = int(num_pieces)
        except ValueError:
            pass
        else:
            break
        t_current = timer()
        if t_current - t_start > timeout:
            raise TimeoutError("Could not find number of pieces")
        time.sleep(0.2)
    return num_pieces


def pickle_profiles(profiles, filename):
    with open(filename, 'bw') as f:
        pickle.dump(profiles, f)


def load_profiles(filename):
    with open(filename, 'rb') as f:
        return pickle.load(f)


def main():
    driver, wait = setup()
    try:
        profiles = get_all_profiles(driver=driver, wait=wait)
        pickle_profiles(profiles, 'profiles_no_num.pickle')
        # profiles = load_profiles('profiles_no_num.pickle')
        for profile in profiles.values():
            num_pieces = get_num_pieces(
                driver=driver,
                wait=wait,
                profile=profile,
            )
            profile.num_pieces = num_pieces
            print(profile)
        pickle_profiles(profiles, 'profiles.pickle')
    finally:
        driver.close()


if __name__ == '__main__':
    main()

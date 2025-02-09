import os
import logging
import requests
from typing import Dict, List, Optional
from woocommerce import API

logger = logging.getLogger(__name__)

class SettingsHandler:
    """מחלקה לניהול הגדרות החנות WooCommerce"""
    
    def __init__(self, wp_url: str):
        """אתחול המחלקה עם כתובת האתר והרשאות"""
        self.wp_url = wp_url
        
        # Initialize WooCommerce API
        wc_key = os.getenv('WC_CONSUMER_KEY')
        wc_secret = os.getenv('WC_CONSUMER_SECRET')
        
        if not wc_key or not wc_secret:
            raise ValueError("WooCommerce API keys not found in environment")
            
        logger.debug(f"Initializing WooCommerce API for settings with URL: {wp_url}")
        self.wcapi = API(
            url=wp_url,
            consumer_key=wc_key,
            consumer_secret=wc_secret,
            version="wc/v3",
            timeout=30
        )
        
    def get_store_info(self) -> Dict:
        """קבלת מידע בסיסי על החנות"""
        try:
            response = self.wcapi.get("system_status")
            if response.status_code != 200:
                raise Exception(f"Failed to get store info: {response.text}")
            return response.json()
        except Exception as e:
            logger.error(f"Error getting store info: {str(e)}")
            raise
            
    def get_payment_gateways(self) -> List[Dict]:
        """קבלת רשימת שערי התשלום המוגדרים"""
        try:
            response = self.wcapi.get("payment_gateways")
            if response.status_code != 200:
                raise Exception(f"Failed to get payment gateways: {response.text}")
            return response.json()
        except Exception as e:
            logger.error(f"Error getting payment gateways: {str(e)}")
            raise
            
    def update_payment_gateway(self, gateway_id: str, **settings) -> Dict:
        """עדכון הגדרות שער תשלום"""
        try:
            response = self.wcapi.put(f"payment_gateways/{gateway_id}", settings)
            if response.status_code != 200:
                raise Exception(f"Failed to update payment gateway: {response.text}")
            return response.json()
        except Exception as e:
            logger.error(f"Error updating payment gateway: {str(e)}")
            raise
            
    def get_tax_rates(self) -> List[Dict]:
        """קבלת רשימת שיעורי המס המוגדרים"""
        try:
            response = self.wcapi.get("taxes")
            if response.status_code != 200:
                raise Exception(f"Failed to get tax rates: {response.text}")
            return response.json()
        except Exception as e:
            logger.error(f"Error getting tax rates: {str(e)}")
            raise
            
    def create_tax_rate(self, country: str, state: str = "", rate: str = "", name: str = "") -> Dict:
        """יצירת שיעור מס חדש"""
        try:
            tax_data = {
                "country": country,
                "state": state,
                "rate": rate,
                "name": name
            }
            
            response = self.wcapi.post("taxes", tax_data)
            if response.status_code != 201:
                raise Exception(f"Failed to create tax rate: {response.text}")
            return response.json()
        except Exception as e:
            logger.error(f"Error creating tax rate: {str(e)}")
            raise
            
    def delete_tax_rate(self, rate_id: int) -> Dict:
        """מחיקת שיעור מס"""
        try:
            response = self.wcapi.delete(f"taxes/{rate_id}", params={"force": True})
            if response.status_code != 200:
                raise Exception(f"Failed to delete tax rate: {response.text}")
            return response.json()
        except Exception as e:
            logger.error(f"Error deleting tax rate: {str(e)}")
            raise
            
    def get_currency_settings(self) -> Dict:
        """קבלת הגדרות מטבע החנות"""
        try:
            response = self.wcapi.get("settings/general/woocommerce_currency")
            if response.status_code != 200:
                raise Exception(f"Failed to get currency settings: {response.text}")
            return response.json()
        except Exception as e:
            logger.error(f"Error getting currency settings: {str(e)}")
            raise
            
    def update_currency_settings(self, currency: str) -> Dict:
        """עדכון מטבע החנות"""
        try:
            response = self.wcapi.put("settings/general/woocommerce_currency", {"value": currency})
            if response.status_code != 200:
                raise Exception(f"Failed to update currency: {response.text}")
            return response.json()
        except Exception as e:
            logger.error(f"Error updating currency: {str(e)}")
            raise 
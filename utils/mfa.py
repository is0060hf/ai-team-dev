"""
多要素認証（MFA）モジュール。
時間ベースのワンタイムパスワード（TOTP）、SMSコード、メールコードなどの
多要素認証機能を提供します。
"""

import os
import base64
import json
import time
import hmac
import hashlib
import secrets
import string
import qrcode
import io
from typing import Dict, List, Any, Optional, Tuple, Union
from datetime import datetime, timedelta

try:
    from utils.logger import get_structured_logger
    logger = get_structured_logger("mfa")
except ImportError:
    import logging
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger("mfa")


class TOTPGenerator:
    """時間ベースのワンタイムパスワード（TOTP）を生成するクラス"""
    
    def __init__(
        self,
        secret_key: Optional[str] = None,
        digits: int = 6,
        interval: int = 30,
        algorithm: str = "sha1"
    ):
        """
        Args:
            secret_key: 秘密鍵（Base32エンコード）
            digits: TOTPの桁数
            interval: TOTP更新間隔（秒）
            algorithm: ハッシュアルゴリズム（sha1, sha256, sha512）
        """
        self.secret_key = secret_key or self.generate_secret_key()
        self.digits = digits
        self.interval = interval
        
        # アルゴリズム選択
        if algorithm.lower() == "sha1":
            self.algorithm = hashlib.sha1
        elif algorithm.lower() == "sha256":
            self.algorithm = hashlib.sha256
        elif algorithm.lower() == "sha512":
            self.algorithm = hashlib.sha512
        else:
            raise ValueError(f"サポートされていないアルゴリズムです: {algorithm}")
    
    @staticmethod
    def generate_secret_key(length: int = 16) -> str:
        """
        TOTPの秘密鍵を生成する
        
        Args:
            length: 秘密鍵の長さ（バイト数）
            
        Returns:
            str: Base32エンコードされた秘密鍵
        """
        # バイナリデータ生成
        random_bytes = secrets.token_bytes(length)
        
        # Base32エンコード
        base32_str = base64.b32encode(random_bytes).decode("utf-8")
        
        return base32_str
    
    def _get_counter(self, timestamp: int = None) -> int:
        """
        現在のカウンター値を計算する
        
        Args:
            timestamp: タイムスタンプ（Noneの場合は現在時刻）
            
        Returns:
            int: カウンター値
        """
        if timestamp is None:
            timestamp = int(time.time())
        
        return timestamp // self.interval
    
    def generate_totp(self, timestamp: int = None) -> str:
        """
        TOTPコードを生成する
        
        Args:
            timestamp: タイムスタンプ（Noneの場合は現在時刻）
            
        Returns:
            str: TOTPコード
        """
        # カウンター値を取得
        counter = self._get_counter(timestamp)
        
        # カウンター値をバイナリ形式に変換
        counter_bytes = counter.to_bytes(8, byteorder="big")
        
        # 秘密鍵をバイナリ形式に変換
        secret_bytes = base64.b32decode(self.secret_key)
        
        # HMAC計算
        hmac_result = hmac.new(secret_bytes, counter_bytes, self.algorithm).digest()
        
        # 動的切り捨て
        offset = hmac_result[-1] & 0x0F
        truncated_hash = ((hmac_result[offset] & 0x7F) << 24 |
                          (hmac_result[offset + 1] & 0xFF) << 16 |
                          (hmac_result[offset + 2] & 0xFF) << 8 |
                          (hmac_result[offset + 3] & 0xFF))
        
        # コードに変換
        code = str(truncated_hash % (10 ** self.digits)).zfill(self.digits)
        
        return code
    
    def verify_totp(self, code: str, valid_window: int = 1) -> bool:
        """
        TOTPコードを検証する
        
        Args:
            code: 検証するTOTPコード
            valid_window: 前後の時間窓の数
            
        Returns:
            bool: コードが有効ならTrue
        """
        if not code or not code.isdigit() or len(code) != self.digits:
            return False
        
        # 現在のタイムスタンプ
        current_timestamp = int(time.time())
        
        # 前後の時間窓を確認
        for i in range(-valid_window, valid_window + 1):
            timestamp = current_timestamp + (i * self.interval)
            if code == self.generate_totp(timestamp):
                return True
        
        return False
    
    def get_provisioning_uri(self, account_name: str, issuer: str = "AppName") -> str:
        """
        OTPアプリケーション（Google Authenticatorなど）用のプロビジョニングURIを生成する
        
        Args:
            account_name: アカウント名（通常はユーザー名やメールアドレス）
            issuer: 発行者名（アプリケーション名）
            
        Returns:
            str: プロビジョニングURI
        """
        import urllib.parse
        
        account_name = urllib.parse.quote(account_name)
        issuer = urllib.parse.quote(issuer)
        
        uri = (f"otpauth://totp/{issuer}:{account_name}?secret={self.secret_key}"
               f"&issuer={issuer}&algorithm={self.algorithm.__name__.upper()}"
               f"&digits={self.digits}&period={self.interval}")
        
        return uri
    
    def generate_qr_code(
        self,
        account_name: str,
        issuer: str = "AppName",
        box_size: int = 6,
        border: int = 4
    ) -> bytes:
        """
        QRコード画像データを生成する
        
        Args:
            account_name: アカウント名
            issuer: 発行者名
            box_size: QRコードのサイズ
            border: QRコードの境界線のサイズ
            
        Returns:
            bytes: PNG形式のイメージデータ
        """
        # プロビジョニングURIを生成
        uri = self.get_provisioning_uri(account_name, issuer)
        
        # QRコードを生成
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=box_size,
            border=border,
        )
        qr.add_data(uri)
        qr.make(fit=True)
        
        # イメージに変換
        img = qr.make_image(fill_color="black", back_color="white")
        
        # バイト配列に変換
        img_byte_array = io.BytesIO()
        img.save(img_byte_array, format='PNG')
        
        return img_byte_array.getvalue()
    
    def time_remaining(self) -> int:
        """
        現在のTOTPが有効な残り時間（秒）を取得する
        
        Returns:
            int: 残り時間（秒）
        """
        current_timestamp = int(time.time())
        current_counter = self._get_counter(current_timestamp)
        next_change = (current_counter + 1) * self.interval
        
        return next_change - current_timestamp


class BackupCodeManager:
    """バックアップコード管理クラス"""
    
    def __init__(self, code_count: int = 10, code_length: int = 8):
        """
        Args:
            code_count: 生成するバックアップコードの数
            code_length: バックアップコードの長さ
        """
        self.code_count = code_count
        self.code_length = code_length
        self.alphabet = string.ascii_uppercase + string.digits
        self.alphabet = self.alphabet.replace("0", "").replace("O", "").replace("1", "").replace("I", "")
    
    def generate_codes(self) -> List[str]:
        """
        バックアップコードを生成する
        
        Returns:
            List[str]: バックアップコードのリスト
        """
        codes = []
        
        for _ in range(self.code_count):
            # ランダムコード生成
            code = ''.join(secrets.choice(self.alphabet) for _ in range(self.code_length))
            
            # 4文字ごとにハイフンを挿入（例: ABCD-EFGH）
            if self.code_length >= 8:
                code = '-'.join([code[i:i+4] for i in range(0, len(code), 4)])
            
            codes.append(code)
        
        return codes
    
    def hash_code(self, code: str, salt: Optional[str] = None) -> Tuple[str, str]:
        """
        バックアップコードをハッシュ化する
        
        Args:
            code: ハッシュ化するコード
            salt: ソルト（Noneの場合は生成）
            
        Returns:
            Tuple[str, str]: ハッシュとソルト
        """
        # ハイフンを削除
        code = code.replace('-', '')
        
        # ソルト生成
        salt = salt or secrets.token_hex(8)
        
        # ハッシュ生成
        hash_obj = hashlib.sha256()
        hash_obj.update((code + salt).encode('utf-8'))
        code_hash = hash_obj.hexdigest()
        
        return code_hash, salt
    
    def verify_code(self, code: str, code_hash: str, salt: str) -> bool:
        """
        バックアップコードを検証する
        
        Args:
            code: 検証するコード
            code_hash: 期待されるハッシュ
            salt: ソルト
            
        Returns:
            bool: コードが一致するならTrue
        """
        # ハイフンを削除
        code = code.replace('-', '')
        
        # ハッシュ化して比較
        calculated_hash, _ = self.hash_code(code, salt)
        
        return calculated_hash == code_hash


class MFAManager:
    """多要素認証（MFA）を管理するクラス"""
    
    def __init__(self, storage_path: str = "storage/mfa"):
        """
        Args:
            storage_path: MFA情報を保存するディレクトリのパス
        """
        self.storage_path = os.path.abspath(storage_path)
        os.makedirs(self.storage_path, exist_ok=True)
        
        # メモリキャッシュ
        self.totp_cache = {}  # user_id -> TOTPGenerator
        self.backup_codes = {}  # user_id -> [{"code_hash": "...", "salt": "...", "used": False}, ...]
        self.sms_codes = {}  # user_id -> {"code": "...", "expires_at": timestamp}
        self.email_codes = {}  # user_id -> {"code": "...", "expires_at": timestamp}
        
        # SMS/メールコード設定
        self.code_length = 6  # SMS/メールコードの桁数
        self.code_validity = 15 * 60  # 15分の有効期間（秒）
        
        logger.info(f"MFAマネージャーを初期化しました。保存先: {self.storage_path}")
    
    def get_user_file_path(self, user_id: str) -> str:
        """ユーザーのMFAファイルパスを取得"""
        user_id_safe = user_id.replace("@", "_at_").replace(".", "_dot_")
        return os.path.join(self.storage_path, f"{user_id_safe}_mfa.json")
    
    def save_user_mfa(self, user_id: str, mfa_data: Dict[str, Any]) -> bool:
        """
        ユーザーのMFA情報を保存する
        
        Args:
            user_id: ユーザーID
            mfa_data: MFAデータ
            
        Returns:
            bool: 成功したらTrue
        """
        try:
            file_path = self.get_user_file_path(user_id)
            
            with open(file_path, "w") as f:
                json.dump(mfa_data, f, indent=2)
            
            logger.info(f"ユーザー {user_id} のMFA情報を保存しました")
            return True
        
        except Exception as e:
            logger.error(f"ユーザー {user_id} のMFA情報の保存に失敗しました: {str(e)}")
            return False
    
    def load_user_mfa(self, user_id: str) -> Optional[Dict[str, Any]]:
        """
        ユーザーのMFA情報を読み込む
        
        Args:
            user_id: ユーザーID
            
        Returns:
            Optional[Dict[str, Any]]: MFAデータ
        """
        try:
            file_path = self.get_user_file_path(user_id)
            
            if not os.path.exists(file_path):
                logger.warning(f"ユーザー {user_id} のMFA情報が見つかりません")
                return None
            
            with open(file_path, "r") as f:
                mfa_data = json.load(f)
            
            return mfa_data
        
        except Exception as e:
            logger.error(f"ユーザー {user_id} のMFA情報の読み込みに失敗しました: {str(e)}")
            return None
    
    def setup_totp(
        self,
        user_id: str,
        account_name: Optional[str] = None,
        issuer: str = "AppName"
    ) -> Dict[str, Any]:
        """
        ユーザーのTOTP認証を設定する
        
        Args:
            user_id: ユーザーID
            account_name: アカウント名（Noneの場合はuser_idを使用）
            issuer: 発行者名
            
        Returns:
            Dict[str, Any]: 設定情報
        """
        # 既存のMFA情報を取得
        mfa_data = self.load_user_mfa(user_id) or {}
        
        # TOTPジェネレーターを作成
        totp_generator = TOTPGenerator()
        
        # キャッシュに追加
        self.totp_cache[user_id] = totp_generator
        
        # MFAデータを更新
        account = account_name or user_id
        totp_data = {
            "secret_key": totp_generator.secret_key,
            "digits": totp_generator.digits,
            "interval": totp_generator.interval,
            "algorithm": totp_generator.algorithm.__name__,
            "verification_status": "pending",  # pending, verified
            "created_at": datetime.now().isoformat()
        }
        
        if "totp" not in mfa_data:
            mfa_data["totp"] = totp_data
        
        if "methods" not in mfa_data:
            mfa_data["methods"] = []
        
        if "totp" not in mfa_data["methods"]:
            mfa_data["methods"].append("totp")
        
        # MFA情報を保存
        self.save_user_mfa(user_id, mfa_data)
        
        # QRコードとプロビジョニングURIを生成
        qr_code = totp_generator.generate_qr_code(account, issuer)
        provisioning_uri = totp_generator.get_provisioning_uri(account, issuer)
        
        # 結果を返す
        result = {
            "secret_key": totp_generator.secret_key,
            "provisioning_uri": provisioning_uri,
            "qr_code": base64.b64encode(qr_code).decode("utf-8"),
            "verification_status": "pending"
        }
        
        logger.info(f"ユーザー {user_id} のTOTP認証を設定しました")
        return result
    
    def verify_totp_setup(self, user_id: str, code: str) -> bool:
        """
        TOTP設定を検証する
        
        Args:
            user_id: ユーザーID
            code: TOTPコード
            
        Returns:
            bool: 検証が成功したらTrue
        """
        # MFA情報を取得
        mfa_data = self.load_user_mfa(user_id)
        if not mfa_data or "totp" not in mfa_data:
            logger.warning(f"ユーザー {user_id} のTOTP情報が見つかりません")
            return False
        
        # TOTPジェネレーターを取得
        totp_generator = self.totp_cache.get(user_id)
        if not totp_generator:
            # キャッシュにない場合は再作成
            totp_data = mfa_data["totp"]
            algorithm = getattr(hashlib, totp_data["algorithm"])
            totp_generator = TOTPGenerator(
                secret_key=totp_data["secret_key"],
                digits=totp_data["digits"],
                interval=totp_data["interval"],
                algorithm=totp_data["algorithm"]
            )
            self.totp_cache[user_id] = totp_generator
        
        # コードを検証
        if totp_generator.verify_totp(code):
            # 検証成功
            mfa_data["totp"]["verification_status"] = "verified"
            mfa_data["totp"]["verified_at"] = datetime.now().isoformat()
            self.save_user_mfa(user_id, mfa_data)
            
            logger.info(f"ユーザー {user_id} のTOTP設定が検証されました")
            return True
        
        logger.warning(f"ユーザー {user_id} のTOTP検証に失敗しました")
        return False
    
    def verify_totp(self, user_id: str, code: str) -> bool:
        """
        TOTPコードを検証する
        
        Args:
            user_id: ユーザーID
            code: TOTPコード
            
        Returns:
            bool: 検証が成功したらTrue
        """
        # MFA情報を取得
        mfa_data = self.load_user_mfa(user_id)
        if not mfa_data or "totp" not in mfa_data:
            logger.warning(f"ユーザー {user_id} のTOTP情報が見つかりません")
            return False
        
        # 検証ステータスを確認
        if mfa_data["totp"]["verification_status"] != "verified":
            logger.warning(f"ユーザー {user_id} のTOTP設定は検証されていません")
            return False
        
        # TOTPジェネレーターを取得
        totp_generator = self.totp_cache.get(user_id)
        if not totp_generator:
            # キャッシュにない場合は再作成
            totp_data = mfa_data["totp"]
            totp_generator = TOTPGenerator(
                secret_key=totp_data["secret_key"],
                digits=totp_data["digits"],
                interval=totp_data["interval"],
                algorithm=totp_data["algorithm"]
            )
            self.totp_cache[user_id] = totp_generator
        
        # コードを検証
        if totp_generator.verify_totp(code):
            logger.info(f"ユーザー {user_id} のTOTP認証が成功しました")
            return True
        
        logger.warning(f"ユーザー {user_id} のTOTP認証に失敗しました")
        return False
    
    def generate_backup_codes(self, user_id: str, code_count: int = 10) -> List[str]:
        """
        バックアップコードを生成する
        
        Args:
            user_id: ユーザーID
            code_count: 生成するコードの数
            
        Returns:
            List[str]: 生成されたバックアップコード
        """
        # MFA情報を取得
        mfa_data = self.load_user_mfa(user_id) or {}
        
        # バックアップコードを生成
        backup_code_manager = BackupCodeManager(code_count=code_count)
        backup_codes = backup_code_manager.generate_codes()
        
        # バックアップコードをハッシュ化して保存
        backup_codes_data = []
        for code in backup_codes:
            code_hash, salt = backup_code_manager.hash_code(code)
            backup_codes_data.append({
                "code_hash": code_hash,
                "salt": salt,
                "used": False,
                "created_at": datetime.now().isoformat()
            })
        
        # MFAデータを更新
        mfa_data["backup_codes"] = backup_codes_data
        
        if "methods" not in mfa_data:
            mfa_data["methods"] = []
        
        if "backup_codes" not in mfa_data["methods"]:
            mfa_data["methods"].append("backup_codes")
        
        # キャッシュに追加
        self.backup_codes[user_id] = backup_codes_data
        
        # MFA情報を保存
        self.save_user_mfa(user_id, mfa_data)
        
        logger.info(f"ユーザー {user_id} のバックアップコードを生成しました")
        return backup_codes
    
    def verify_backup_code(self, user_id: str, code: str) -> bool:
        """
        バックアップコードを検証する
        
        Args:
            user_id: ユーザーID
            code: バックアップコード
            
        Returns:
            bool: 検証が成功したらTrue
        """
        # MFA情報を取得
        mfa_data = self.load_user_mfa(user_id)
        if not mfa_data or "backup_codes" not in mfa_data:
            logger.warning(f"ユーザー {user_id} のバックアップコード情報が見つかりません")
            return False
        
        # バックアップコードマネージャーを作成
        backup_code_manager = BackupCodeManager()
        
        # バックアップコードをチェック
        backup_codes_data = mfa_data["backup_codes"]
        
        for i, code_data in enumerate(backup_codes_data):
            # 既に使用済みのコードは無視
            if code_data["used"]:
                continue
            
            # コードを検証
            if backup_code_manager.verify_code(code, code_data["code_hash"], code_data["salt"]):
                # 使用済みにマーク
                backup_codes_data[i]["used"] = True
                backup_codes_data[i]["used_at"] = datetime.now().isoformat()
                
                # MFA情報を保存
                self.save_user_mfa(user_id, mfa_data)
                
                # キャッシュも更新
                if user_id in self.backup_codes:
                    self.backup_codes[user_id] = backup_codes_data
                
                logger.info(f"ユーザー {user_id} がバックアップコードを使用しました")
                return True
        
        logger.warning(f"ユーザー {user_id} のバックアップコード検証に失敗しました")
        return False
    
    def generate_sms_code(self, user_id: str, phone_number: str) -> str:
        """
        SMS認証コードを生成する
        
        Args:
            user_id: ユーザーID
            phone_number: 電話番号
            
        Returns:
            str: 生成されたコード
        """
        # MFA情報を取得
        mfa_data = self.load_user_mfa(user_id) or {}
        
        # コードを生成
        code = ''.join(secrets.choice(string.digits) for _ in range(self.code_length))
        
        # 有効期限を設定
        expires_at = datetime.now() + timedelta(seconds=self.code_validity)
        
        # MFAデータを更新
        if "sms" not in mfa_data:
            mfa_data["sms"] = {}
        
        mfa_data["sms"]["phone_number"] = phone_number
        mfa_data["sms"]["code_hash"] = hashlib.sha256(code.encode()).hexdigest()
        mfa_data["sms"]["expires_at"] = expires_at.isoformat()
        mfa_data["sms"]["attempts"] = 0
        
        if "methods" not in mfa_data:
            mfa_data["methods"] = []
        
        if "sms" not in mfa_data["methods"]:
            mfa_data["methods"].append("sms")
        
        # キャッシュに追加
        self.sms_codes[user_id] = {
            "code": code,
            "expires_at": expires_at.timestamp()
        }
        
        # MFA情報を保存
        self.save_user_mfa(user_id, mfa_data)
        
        logger.info(f"ユーザー {user_id} のSMS認証コードを生成しました")
        return code
    
    def verify_sms_code(self, user_id: str, code: str, max_attempts: int = 3) -> bool:
        """
        SMS認証コードを検証する
        
        Args:
            user_id: ユーザーID
            code: SMS認証コード
            max_attempts: 最大試行回数
            
        Returns:
            bool: 検証が成功したらTrue
        """
        # MFA情報を取得
        mfa_data = self.load_user_mfa(user_id)
        if not mfa_data or "sms" not in mfa_data:
            logger.warning(f"ユーザー {user_id} のSMS情報が見つかりません")
            return False
        
        # 有効期限をチェック
        sms_data = mfa_data["sms"]
        expires_at = datetime.fromisoformat(sms_data["expires_at"])
        
        if datetime.now() > expires_at:
            logger.warning(f"ユーザー {user_id} のSMS認証コードは期限切れです")
            return False
        
        # 試行回数をチェック
        attempts = sms_data.get("attempts", 0)
        if attempts >= max_attempts:
            logger.warning(f"ユーザー {user_id} のSMS認証コードの試行回数が上限に達しました")
            return False
        
        # コードを検証
        cached_code = None
        if user_id in self.sms_codes:
            cached_code = self.sms_codes[user_id]["code"]
        
        code_hash = hashlib.sha256(code.encode()).hexdigest()
        
        if code_hash == sms_data["code_hash"] or (cached_code and code == cached_code):
            # 検証成功
            mfa_data["sms"]["verified_at"] = datetime.now().isoformat()
            mfa_data["sms"]["attempts"] = 0
            self.save_user_mfa(user_id, mfa_data)
            
            # キャッシュから削除
            if user_id in self.sms_codes:
                del self.sms_codes[user_id]
            
            logger.info(f"ユーザー {user_id} のSMS認証が成功しました")
            return True
        
        # 試行回数を増やす
        mfa_data["sms"]["attempts"] = attempts + 1
        self.save_user_mfa(user_id, mfa_data)
        
        logger.warning(f"ユーザー {user_id} のSMS認証に失敗しました（試行: {attempts + 1}/{max_attempts}）")
        return False
    
    def generate_email_code(self, user_id: str, email: str) -> str:
        """
        メール認証コードを生成する
        
        Args:
            user_id: ユーザーID
            email: メールアドレス
            
        Returns:
            str: 生成されたコード
        """
        # MFA情報を取得
        mfa_data = self.load_user_mfa(user_id) or {}
        
        # コードを生成
        code = ''.join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(self.code_length))
        
        # 有効期限を設定
        expires_at = datetime.now() + timedelta(seconds=self.code_validity)
        
        # MFAデータを更新
        if "email" not in mfa_data:
            mfa_data["email"] = {}
        
        mfa_data["email"]["email"] = email
        mfa_data["email"]["code_hash"] = hashlib.sha256(code.encode()).hexdigest()
        mfa_data["email"]["expires_at"] = expires_at.isoformat()
        mfa_data["email"]["attempts"] = 0
        
        if "methods" not in mfa_data:
            mfa_data["methods"] = []
        
        if "email" not in mfa_data["methods"]:
            mfa_data["methods"].append("email")
        
        # キャッシュに追加
        self.email_codes[user_id] = {
            "code": code,
            "expires_at": expires_at.timestamp()
        }
        
        # MFA情報を保存
        self.save_user_mfa(user_id, mfa_data)
        
        logger.info(f"ユーザー {user_id} のメール認証コードを生成しました")
        return code
    
    def verify_email_code(self, user_id: str, code: str, max_attempts: int = 3) -> bool:
        """
        メール認証コードを検証する
        
        Args:
            user_id: ユーザーID
            code: メール認証コード
            max_attempts: 最大試行回数
            
        Returns:
            bool: 検証が成功したらTrue
        """
        # MFA情報を取得
        mfa_data = self.load_user_mfa(user_id)
        if not mfa_data or "email" not in mfa_data:
            logger.warning(f"ユーザー {user_id} のメール情報が見つかりません")
            return False
        
        # 有効期限をチェック
        email_data = mfa_data["email"]
        expires_at = datetime.fromisoformat(email_data["expires_at"])
        
        if datetime.now() > expires_at:
            logger.warning(f"ユーザー {user_id} のメール認証コードは期限切れです")
            return False
        
        # 試行回数をチェック
        attempts = email_data.get("attempts", 0)
        if attempts >= max_attempts:
            logger.warning(f"ユーザー {user_id} のメール認証コードの試行回数が上限に達しました")
            return False
        
        # コードを検証
        cached_code = None
        if user_id in self.email_codes:
            cached_code = self.email_codes[user_id]["code"]
        
        code_hash = hashlib.sha256(code.encode()).hexdigest()
        
        if code_hash == email_data["code_hash"] or (cached_code and code == cached_code):
            # 検証成功
            mfa_data["email"]["verified_at"] = datetime.now().isoformat()
            mfa_data["email"]["attempts"] = 0
            self.save_user_mfa(user_id, mfa_data)
            
            # キャッシュから削除
            if user_id in self.email_codes:
                del self.email_codes[user_id]
            
            logger.info(f"ユーザー {user_id} のメール認証が成功しました")
            return True
        
        # 試行回数を増やす
        mfa_data["email"]["attempts"] = attempts + 1
        self.save_user_mfa(user_id, mfa_data)
        
        logger.warning(f"ユーザー {user_id} のメール認証に失敗しました（試行: {attempts + 1}/{max_attempts}）")
        return False
    
    def get_enabled_methods(self, user_id: str) -> List[str]:
        """
        ユーザーの有効なMFA方法を取得する
        
        Args:
            user_id: ユーザーID
            
        Returns:
            List[str]: 有効なMFA方法のリスト
        """
        # MFA情報を取得
        mfa_data = self.load_user_mfa(user_id)
        if not mfa_data or "methods" not in mfa_data:
            return []
        
        # 有効なメソッドを確認
        methods = []
        for method in mfa_data["methods"]:
            if method == "totp":
                if "totp" in mfa_data and mfa_data["totp"].get("verification_status") == "verified":
                    methods.append("totp")
            elif method == "backup_codes":
                if "backup_codes" in mfa_data:
                    # 未使用のバックアップコードがあるか確認
                    unused_codes = [code for code in mfa_data["backup_codes"] if not code.get("used", False)]
                    if unused_codes:
                        methods.append("backup_codes")
            elif method == "sms":
                if "sms" in mfa_data and "phone_number" in mfa_data["sms"]:
                    methods.append("sms")
            elif method == "email":
                if "email" in mfa_data and "email" in mfa_data["email"]:
                    methods.append("email")
        
        return methods
    
    def disable_method(self, user_id: str, method: str) -> bool:
        """
        MFA方法を無効化する
        
        Args:
            user_id: ユーザーID
            method: 無効化する方法
            
        Returns:
            bool: 成功したらTrue
        """
        # MFA情報を取得
        mfa_data = self.load_user_mfa(user_id)
        if not mfa_data:
            logger.warning(f"ユーザー {user_id} のMFA情報が見つかりません")
            return False
        
        # メソッドを無効化
        if "methods" in mfa_data and method in mfa_data["methods"]:
            mfa_data["methods"].remove(method)
            
            # メソッド固有のデータを削除
            if method in mfa_data:
                del mfa_data[method]
            
            # キャッシュから削除
            if method == "totp" and user_id in self.totp_cache:
                del self.totp_cache[user_id]
            elif method == "backup_codes" and user_id in self.backup_codes:
                del self.backup_codes[user_id]
            elif method == "sms" and user_id in self.sms_codes:
                del self.sms_codes[user_id]
            elif method == "email" and user_id in self.email_codes:
                del self.email_codes[user_id]
            
            # MFA情報を保存
            self.save_user_mfa(user_id, mfa_data)
            
            logger.info(f"ユーザー {user_id} の {method} 認証を無効化しました")
            return True
        
        logger.warning(f"ユーザー {user_id} の {method} 認証は有効ではありません")
        return False
    
    def get_remaining_backup_codes(self, user_id: str) -> int:
        """
        残りのバックアップコード数を取得する
        
        Args:
            user_id: ユーザーID
            
        Returns:
            int: 残りのバックアップコード数
        """
        # MFA情報を取得
        mfa_data = self.load_user_mfa(user_id)
        if not mfa_data or "backup_codes" not in mfa_data:
            return 0
        
        # 未使用のバックアップコード数をカウント
        unused_codes = [code for code in mfa_data["backup_codes"] if not code.get("used", False)]
        return len(unused_codes)


# シングルトンインスタンス
mfa_manager = MFAManager()


# ヘルパー関数
def setup_totp(user_id: str, account_name: Optional[str] = None, issuer: str = "AppName") -> Dict[str, Any]:
    """
    TOTP認証を設定するヘルパー関数
    
    Args:
        user_id: ユーザーID
        account_name: アカウント名
        issuer: 発行者名
        
    Returns:
        Dict[str, Any]: 設定情報
    """
    return mfa_manager.setup_totp(user_id, account_name, issuer)


def verify_totp_setup(user_id: str, code: str) -> bool:
    """
    TOTP設定を検証するヘルパー関数
    
    Args:
        user_id: ユーザーID
        code: TOTPコード
        
    Returns:
        bool: 成功したらTrue
    """
    return mfa_manager.verify_totp_setup(user_id, code)


def verify_totp(user_id: str, code: str) -> bool:
    """
    TOTPコードを検証するヘルパー関数
    
    Args:
        user_id: ユーザーID
        code: TOTPコード
        
    Returns:
        bool: 成功したらTrue
    """
    return mfa_manager.verify_totp(user_id, code)


def generate_backup_codes(user_id: str, code_count: int = 10) -> List[str]:
    """
    バックアップコードを生成するヘルパー関数
    
    Args:
        user_id: ユーザーID
        code_count: 生成するコード数
        
    Returns:
        List[str]: バックアップコード
    """
    return mfa_manager.generate_backup_codes(user_id, code_count)


def verify_backup_code(user_id: str, code: str) -> bool:
    """
    バックアップコードを検証するヘルパー関数
    
    Args:
        user_id: ユーザーID
        code: バックアップコード
        
    Returns:
        bool: 成功したらTrue
    """
    return mfa_manager.verify_backup_code(user_id, code)


def generate_sms_code(user_id: str, phone_number: str) -> str:
    """
    SMS認証コードを生成するヘルパー関数
    
    Args:
        user_id: ユーザーID
        phone_number: 電話番号
        
    Returns:
        str: 生成されたコード
    """
    return mfa_manager.generate_sms_code(user_id, phone_number)


def verify_sms_code(user_id: str, code: str, max_attempts: int = 3) -> bool:
    """
    SMS認証コードを検証するヘルパー関数
    
    Args:
        user_id: ユーザーID
        code: SMS認証コード
        max_attempts: 最大試行回数
        
    Returns:
        bool: 成功したらTrue
    """
    return mfa_manager.verify_sms_code(user_id, code, max_attempts)


def generate_email_code(user_id: str, email: str) -> str:
    """
    メール認証コードを生成するヘルパー関数
    
    Args:
        user_id: ユーザーID
        email: メールアドレス
        
    Returns:
        str: 生成されたコード
    """
    return mfa_manager.generate_email_code(user_id, email)


def verify_email_code(user_id: str, code: str, max_attempts: int = 3) -> bool:
    """
    メール認証コードを検証するヘルパー関数
    
    Args:
        user_id: ユーザーID
        code: メール認証コード
        max_attempts: 最大試行回数
        
    Returns:
        bool: 成功したらTrue
    """
    return mfa_manager.verify_email_code(user_id, code, max_attempts)


def get_enabled_methods(user_id: str) -> List[str]:
    """
    ユーザーの有効なMFA方法を取得するヘルパー関数
    
    Args:
        user_id: ユーザーID
        
    Returns:
        List[str]: 有効なMFA方法のリスト
    """
    return mfa_manager.get_enabled_methods(user_id)


def disable_method(user_id: str, method: str) -> bool:
    """
    MFA方法を無効化するヘルパー関数
    
    Args:
        user_id: ユーザーID
        method: 無効化する方法
        
    Returns:
        bool: 成功したらTrue
    """
    return mfa_manager.disable_method(user_id, method)


def get_remaining_backup_codes(user_id: str) -> int:
    """
    残りのバックアップコード数を取得するヘルパー関数
    
    Args:
        user_id: ユーザーID
        
    Returns:
        int: 残りのバックアップコード数
    """
    return mfa_manager.get_remaining_backup_codes(user_id) 
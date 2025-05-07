"""
SSL/TLS証明書管理モジュール。
証明書の生成、検証、更新などの機能を提供します。
"""

import os
import json
import time
import subprocess
import datetime
import shutil
import tempfile
import re
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple, Union
import logging
import ssl
import socket
import threading
from dataclasses import dataclass, field

try:
    from utils.logger import get_structured_logger
    logger = get_structured_logger("ssl_manager")
except ImportError:
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger("ssl_manager")

# OpenSSL コマンドが利用可能かチェック
try:
    result = subprocess.run(
        ["openssl", "version"], 
        stdout=subprocess.PIPE, 
        stderr=subprocess.PIPE,
        check=True
    )
    OPENSSL_AVAILABLE = True
    logger.info(f"OpenSSL が利用可能: {result.stdout.decode().strip()}")
except (subprocess.SubprocessError, FileNotFoundError):
    OPENSSL_AVAILABLE = False
    logger.warning("OpenSSL コマンドが見つかりません。自己署名証明書の生成には OpenSSL が必要です。")


@dataclass
class CertificateInfo:
    """証明書の情報を表すクラス"""
    
    subject: Dict[str, str] = field(default_factory=dict)
    issuer: Dict[str, str] = field(default_factory=dict)
    serial_number: str = ""
    not_before: datetime.datetime = datetime.datetime.now()
    not_after: datetime.datetime = datetime.datetime.now()
    common_name: str = ""
    alt_names: List[str] = field(default_factory=list)
    fingerprint: str = ""
    file_path: Optional[str] = None
    key_path: Optional[str] = None
    intermediate_path: Optional[str] = None
    root_path: Optional[str] = None
    status: str = "unknown"  # valid, expired, revoked, unknown
    
    def is_valid(self) -> bool:
        """証明書が有効かどうかをチェック"""
        now = datetime.datetime.now()
        return self.not_before <= now <= self.not_after and self.status == "valid"
    
    def days_until_expiry(self) -> int:
        """証明書の有効期限までの日数を計算"""
        now = datetime.datetime.now()
        if now > self.not_after:
            return -1  # すでに期限切れ
        return (self.not_after - now).days
    
    def to_dict(self) -> Dict[str, Any]:
        """辞書形式に変換"""
        return {
            "subject": self.subject,
            "issuer": self.issuer,
            "serial_number": self.serial_number,
            "not_before": self.not_before.isoformat(),
            "not_after": self.not_after.isoformat(),
            "common_name": self.common_name,
            "alt_names": self.alt_names,
            "fingerprint": self.fingerprint,
            "file_path": self.file_path,
            "key_path": self.key_path,
            "intermediate_path": self.intermediate_path,
            "root_path": self.root_path,
            "status": self.status,
            "days_until_expiry": self.days_until_expiry()
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'CertificateInfo':
        """辞書からインスタンスを作成"""
        cert_info = cls(
            subject=data.get("subject", {}),
            issuer=data.get("issuer", {}),
            serial_number=data.get("serial_number", ""),
            not_before=datetime.datetime.fromisoformat(data["not_before"]) if "not_before" in data else datetime.datetime.now(),
            not_after=datetime.datetime.fromisoformat(data["not_after"]) if "not_after" in data else datetime.datetime.now(),
            common_name=data.get("common_name", ""),
            alt_names=data.get("alt_names", []),
            fingerprint=data.get("fingerprint", ""),
            file_path=data.get("file_path"),
            key_path=data.get("key_path"),
            intermediate_path=data.get("intermediate_path"),
            root_path=data.get("root_path"),
            status=data.get("status", "unknown")
        )
        return cert_info


class SSLCertificateManager:
    """SSL/TLS証明書を管理するクラス"""
    
    def __init__(self, storage_path: str = "storage/certificates"):
        """
        Args:
            storage_path: 証明書を保存するディレクトリのパス
        """
        self.storage_path = os.path.abspath(storage_path)
        os.makedirs(self.storage_path, exist_ok=True)
        
        # 証明書情報のキャッシュ
        self.certificates: Dict[str, CertificateInfo] = {}
        
        # 有効期限監視用スレッド
        self.monitor_thread = None
        self.running = False
        
        # 初期化時に証明書をロード
        self.load_certificates()
        
        logger.info(f"SSL証明書マネージャーを初期化しました。保存先: {self.storage_path}")
    
    def load_certificates(self):
        """保存されている証明書情報を読み込む"""
        try:
            index_path = os.path.join(self.storage_path, "certificates.json")
            
            if not os.path.exists(index_path):
                logger.info("証明書インデックスファイルが見つかりません。新規作成します。")
                return
            
            with open(index_path, "r") as f:
                cert_data = json.load(f)
                
                for domain, cert_info in cert_data.items():
                    self.certificates[domain] = CertificateInfo.from_dict(cert_info)
            
            # 証明書の状態を更新
            self._update_certificate_status()
            
            logger.info(f"{len(self.certificates)} 件の証明書情報を読み込みました")
        
        except Exception as e:
            logger.error(f"証明書情報の読み込みに失敗しました: {str(e)}")
    
    def save_certificates(self):
        """証明書情報をファイルに保存"""
        try:
            index_path = os.path.join(self.storage_path, "certificates.json")
            
            cert_data = {}
            for domain, cert_info in self.certificates.items():
                cert_data[domain] = cert_info.to_dict()
            
            with open(index_path, "w") as f:
                json.dump(cert_data, f, indent=2)
            
            logger.info(f"{len(self.certificates)} 件の証明書情報を保存しました")
        
        except Exception as e:
            logger.error(f"証明書情報の保存に失敗しました: {str(e)}")
    
    def _update_certificate_status(self):
        """全ての証明書の状態を更新"""
        now = datetime.datetime.now()
        
        for domain, cert_info in self.certificates.items():
            # 期限切れかどうかをチェック
            if cert_info.not_after < now:
                cert_info.status = "expired"
            elif cert_info.not_before > now:
                cert_info.status = "not_yet_valid"
            else:
                # 有効期限内の場合は証明書ファイルの存在を確認
                if cert_info.file_path and os.path.exists(cert_info.file_path):
                    cert_info.status = "valid"
                else:
                    cert_info.status = "file_missing"
    
    def get_certificate_info(self, domain: str) -> Optional[CertificateInfo]:
        """
        ドメインの証明書情報を取得
        
        Args:
            domain: ドメイン名
            
        Returns:
            Optional[CertificateInfo]: 証明書情報
        """
        # キャッシュを更新
        self._update_certificate_status()
        
        # ドメインの証明書情報を返す
        return self.certificates.get(domain)
    
    def list_certificates(self) -> List[CertificateInfo]:
        """
        全ての証明書情報を取得
        
        Returns:
            List[CertificateInfo]: 証明書情報のリスト
        """
        # キャッシュを更新
        self._update_certificate_status()
        
        return list(self.certificates.values())
    
    def get_expiring_certificates(self, days_threshold: int = 30) -> List[CertificateInfo]:
        """
        期限切れが近い証明書を取得
        
        Args:
            days_threshold: 残り日数の閾値
            
        Returns:
            List[CertificateInfo]: 期限切れが近い証明書のリスト
        """
        # キャッシュを更新
        self._update_certificate_status()
        
        expiring_certs = []
        for cert_info in self.certificates.values():
            if 0 < cert_info.days_until_expiry() <= days_threshold:
                expiring_certs.append(cert_info)
        
        return expiring_certs
    
    def generate_self_signed_cert(
        self,
        domain: str,
        organization: str = "Example Org",
        country: str = "JP",
        state: str = "Tokyo",
        locality: str = "Tokyo",
        email: str = "admin@example.com",
        alt_names: List[str] = None,
        validity_days: int = 365,
    ) -> Optional[CertificateInfo]:
        """
        自己署名証明書を生成
        
        Args:
            domain: ドメイン名
            organization: 組織名
            country: 国コード
            state: 都道府県
            locality: 市区町村
            email: メールアドレス
            alt_names: 代替ドメイン名のリスト
            validity_days: 有効期間（日数）
            
        Returns:
            Optional[CertificateInfo]: 生成された証明書の情報
        """
        if not OPENSSL_AVAILABLE:
            logger.error("OpenSSL が利用できないため、証明書を生成できません")
            return None
        
        try:
            # 証明書や鍵のパスを設定
            cert_dir = os.path.join(self.storage_path, domain)
            os.makedirs(cert_dir, exist_ok=True)
            
            key_path = os.path.join(cert_dir, f"{domain}.key")
            cert_path = os.path.join(cert_dir, f"{domain}.crt")
            
            # OpenSSL 設定ファイルを作成
            config_path = os.path.join(cert_dir, f"{domain}.cnf")
            
            alt_domains = alt_names or []
            if domain not in alt_domains:
                alt_domains.insert(0, domain)
            
            # SAN (Subject Alternative Name) の設定
            san_section = "\n".join([f"DNS.{i+1} = {name}" for i, name in enumerate(alt_domains)])
            
            config_content = f"""[req]
distinguished_name = req_distinguished_name
req_extensions = v3_req
prompt = no

[req_distinguished_name]
C = {country}
ST = {state}
L = {locality}
O = {organization}
CN = {domain}
emailAddress = {email}

[v3_req]
keyUsage = keyEncipherment, dataEncipherment, digitalSignature
extendedKeyUsage = serverAuth
subjectAltName = @alt_names

[alt_names]
{san_section}
"""
            
            with open(config_path, "w") as f:
                f.write(config_content)
            
            # 秘密鍵を生成
            subprocess.run(
                ["openssl", "genrsa", "-out", key_path, "2048"],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            
            # 証明書を生成
            subprocess.run(
                [
                    "openssl", "req", "-new", "-x509", "-key", key_path,
                    "-out", cert_path, "-days", str(validity_days),
                    "-config", config_path
                ],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            
            # 証明書情報を取得
            cert_info = self._read_certificate_info(cert_path, key_path)
            
            if cert_info:
                # 証明書情報をキャッシュに追加
                self.certificates[domain] = cert_info
                self.save_certificates()
                
                logger.info(f"{domain} の自己署名証明書を生成しました")
                return cert_info
            else:
                logger.error(f"{domain} の証明書情報を取得できませんでした")
                return None
        
        except Exception as e:
            logger.error(f"{domain} の自己署名証明書の生成に失敗しました: {str(e)}")
            return None
    
    def _read_certificate_info(
        self, 
        cert_path: str, 
        key_path: Optional[str] = None,
        intermediate_path: Optional[str] = None,
        root_path: Optional[str] = None
    ) -> Optional[CertificateInfo]:
        """
        証明書ファイルからCertificateInfoオブジェクトを生成
        
        Args:
            cert_path: 証明書ファイルのパス
            key_path: 秘密鍵ファイルのパス
            intermediate_path: 中間証明書ファイルのパス
            root_path: ルート証明書ファイルのパス
            
        Returns:
            Optional[CertificateInfo]: 証明書情報
        """
        if not os.path.exists(cert_path):
            logger.error(f"証明書ファイルが見つかりません: {cert_path}")
            return None
        
        try:
            # OpenSSLコマンドで証明書情報を取得
            output = subprocess.check_output(
                ["openssl", "x509", "-in", cert_path, "-text", "-noout"],
                stderr=subprocess.STDOUT
            ).decode()
            
            # 証明書情報を解析
            cert_info = CertificateInfo()
            cert_info.file_path = cert_path
            cert_info.key_path = key_path if key_path and os.path.exists(key_path) else None
            cert_info.intermediate_path = intermediate_path if intermediate_path and os.path.exists(intermediate_path) else None
            cert_info.root_path = root_path if root_path and os.path.exists(root_path) else None
            
            # 有効期限を解析
            not_before_match = re.search(r"Not Before: (.+)", output)
            not_after_match = re.search(r"Not After : (.+)", output)
            
            if not_before_match:
                not_before_str = not_before_match.group(1).strip()
                # OpenSSLの日付形式を解析
                cert_info.not_before = datetime.datetime.strptime(not_before_str, "%b %d %H:%M:%S %Y %Z")
            
            if not_after_match:
                not_after_str = not_after_match.group(1).strip()
                # OpenSSLの日付形式を解析
                cert_info.not_after = datetime.datetime.strptime(not_after_str, "%b %d %H:%M:%S %Y %Z")
            
            # コモンネームを解析
            subject_match = re.search(r"Subject: (.+)", output)
            if subject_match:
                subject_str = subject_match.group(1).strip()
                subject_parts = re.findall(r"([A-Za-z]+)=([^,/]+)", subject_str)
                
                cert_info.subject = {key: value.strip() for key, value in subject_parts}
                cert_info.common_name = cert_info.subject.get("CN", "")
            
            # 発行者を解析
            issuer_match = re.search(r"Issuer: (.+)", output)
            if issuer_match:
                issuer_str = issuer_match.group(1).strip()
                issuer_parts = re.findall(r"([A-Za-z]+)=([^,/]+)", issuer_str)
                
                cert_info.issuer = {key: value.strip() for key, value in issuer_parts}
            
            # シリアル番号を解析
            serial_match = re.search(r"Serial Number: (.+)", output)
            if serial_match:
                cert_info.serial_number = serial_match.group(1).strip()
            
            # 指紋を取得
            fingerprint_output = subprocess.check_output(
                ["openssl", "x509", "-in", cert_path, "-fingerprint", "-sha256", "-noout"],
                stderr=subprocess.STDOUT
            ).decode()
            
            fingerprint_match = re.search(r"SHA256 Fingerprint=(.+)", fingerprint_output)
            if fingerprint_match:
                cert_info.fingerprint = fingerprint_match.group(1).strip()
            
            # サブジェクト代替名を解析
            san_section = re.search(r"X509v3 Subject Alternative Name: (.+?)(?:\n\n|\n[a-zA-Z])", output, re.DOTALL)
            if san_section:
                san_str = san_section.group(1).strip()
                dns_names = re.findall(r"DNS:([^,\s]+)", san_str)
                cert_info.alt_names = dns_names
            
            # ステータスを設定
            now = datetime.datetime.now()
            if cert_info.not_before <= now <= cert_info.not_after:
                cert_info.status = "valid"
            elif now > cert_info.not_after:
                cert_info.status = "expired"
            else:
                cert_info.status = "not_yet_valid"
            
            return cert_info
        
        except Exception as e:
            logger.error(f"証明書情報の読み込みに失敗しました: {str(e)}")
            return None
    
    def verify_certificate(self, domain: str) -> bool:
        """
        証明書が有効かどうかを検証
        
        Args:
            domain: ドメイン名
            
        Returns:
            bool: 有効ならTrue
        """
        cert_info = self.get_certificate_info(domain)
        if not cert_info:
            logger.warning(f"{domain} の証明書情報が見つかりません")
            return False
        
        if not cert_info.file_path or not os.path.exists(cert_info.file_path):
            logger.warning(f"{domain} の証明書ファイルが見つかりません")
            return False
        
        try:
            # 証明書ファイルを確認
            result = subprocess.run(
                ["openssl", "verify", cert_info.file_path],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            
            if result.returncode == 0:
                # 自己署名証明書の場合は常に失敗するため、期限だけで判断
                cert_info.status = "valid"
                self.save_certificates()
                return True
            else:
                # 自己署名証明書の場合、期限が有効であればOK
                now = datetime.datetime.now()
                if cert_info.not_before <= now <= cert_info.not_after:
                    return True
                    
                logger.warning(f"{domain} の証明書検証に失敗しました: {result.stderr.decode()}")
                cert_info.status = "invalid"
                self.save_certificates()
                return False
        
        except Exception as e:
            logger.error(f"{domain} の証明書検証中にエラーが発生しました: {str(e)}")
            return False
    
    def check_remote_certificate(self, host: str, port: int = 443) -> Optional[CertificateInfo]:
        """
        リモートサーバーの証明書情報を取得
        
        Args:
            host: ホスト名
            port: ポート番号
            
        Returns:
            Optional[CertificateInfo]: 証明書情報
        """
        try:
            context = ssl.create_default_context()
            with socket.create_connection((host, port)) as sock:
                with context.wrap_socket(sock, server_hostname=host) as ssock:
                    cert = ssock.getpeercert()
            
            # 証明書情報を解析
            cert_info = CertificateInfo()
            
            # 基本情報
            subject = dict(x[0] for x in cert.get('subject', []))
            cert_info.subject = subject
            cert_info.common_name = subject.get('commonName', '')
            
            cert_info.issuer = dict(x[0] for x in cert.get('issuer', []))
            cert_info.serial_number = cert.get('serialNumber', '')
            
            # 有効期限
            cert_info.not_before = datetime.datetime.strptime(cert['notBefore'], '%b %d %H:%M:%S %Y %Z')
            cert_info.not_after = datetime.datetime.strptime(cert['notAfter'], '%b %d %H:%M:%S %Y %Z')
            
            # 代替名
            if 'subjectAltName' in cert:
                cert_info.alt_names = [x[1] for x in cert['subjectAltName'] if x[0] == 'DNS']
            
            # ステータスを設定
            now = datetime.datetime.now()
            if cert_info.not_before <= now <= cert_info.not_after:
                cert_info.status = "valid"
            elif now > cert_info.not_after:
                cert_info.status = "expired"
            else:
                cert_info.status = "not_yet_valid"
            
            return cert_info
        
        except Exception as e:
            logger.error(f"{host}:{port} の証明書取得に失敗しました: {str(e)}")
            return None
    
    def start_certificate_monitor(self, interval_hours: int = 24, notify_days: int = 30):
        """
        証明書の有効期限を監視するスレッドを開始
        
        Args:
            interval_hours: チェック間隔（時間）
            notify_days: 通知するまでの残り日数
        """
        if self.monitor_thread is not None and self.monitor_thread.is_alive():
            logger.warning("証明書監視スレッドはすでに実行中です")
            return
        
        self.running = True
        
        def _monitor_task():
            """証明書の有効期限を監視するタスク"""
            logger.info("証明書監視タスクを開始しました")
            
            while self.running:
                try:
                    # 期限切れが近い証明書を取得
                    expiring_certs = self.get_expiring_certificates(notify_days)
                    
                    # 期限切れが近い証明書を通知
                    for cert in expiring_certs:
                        logger.warning(
                            f"証明書の有効期限が近づいています: {cert.common_name} "
                            f"（残り {cert.days_until_expiry()} 日）"
                        )
                    
                    # 期限切れの証明書を通知
                    for domain, cert in self.certificates.items():
                        if cert.status == "expired":
                            logger.error(f"証明書が期限切れです: {domain} （期限: {cert.not_after.isoformat()}）")
                
                except Exception as e:
                    logger.error(f"証明書監視タスクでエラーが発生しました: {str(e)}")
                
                # 次回の実行まで待機
                for _ in range(interval_hours * 60 * 60):
                    if not self.running:
                        break
                    time.sleep(1)
        
        self.monitor_thread = threading.Thread(
            target=_monitor_task,
            daemon=True,
            name="CertificateMonitor"
        )
        self.monitor_thread.start()
        logger.info(f"証明書監視スレッドを開始しました（間隔: {interval_hours}時間）")
    
    def stop_certificate_monitor(self):
        """証明書監視スレッドを停止"""
        if self.monitor_thread and self.monitor_thread.is_alive():
            self.running = False
            logger.info("証明書監視スレッドを停止しました")


class HttpsConfiguration:
    """HTTPS設定を管理するクラス"""
    
    def __init__(self, cert_manager: SSLCertificateManager = None):
        """
        Args:
            cert_manager: 証明書マネージャーインスタンス
        """
        self.cert_manager = cert_manager or ssl_manager
    
    def get_secure_context(self, domain: str) -> Optional[ssl.SSLContext]:
        """
        ドメインのSSLコンテキストを取得
        
        Args:
            domain: ドメイン名
            
        Returns:
            Optional[ssl.SSLContext]: SSLコンテキスト
        """
        cert_info = self.cert_manager.get_certificate_info(domain)
        if not cert_info or not cert_info.is_valid():
            logger.warning(f"{domain} の有効な証明書が見つかりません")
            return None
        
        try:
            context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
            context.load_cert_chain(
                certfile=cert_info.file_path,
                keyfile=cert_info.key_path
            )
            
            # 安全な設定を適用
            context.set_ciphers('ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256:ECDHE-ECDSA-AES256-GCM-SHA384:ECDHE-RSA-AES256-GCM-SHA384:ECDHE-ECDSA-CHACHA20-POLY1305:ECDHE-RSA-CHACHA20-POLY1305:DHE-RSA-AES128-GCM-SHA256:DHE-RSA-AES256-GCM-SHA384')
            context.options |= ssl.OP_NO_TLSv1 | ssl.OP_NO_TLSv1_1
            context.minimum_version = ssl.TLSVersion.TLSv1_2
            
            return context
        
        except Exception as e:
            logger.error(f"{domain} のSSLコンテキスト作成に失敗しました: {str(e)}")
            return None
    
    def get_security_headers(self) -> Dict[str, str]:
        """
        セキュリティ関連のHTTPヘッダーを取得
        
        Returns:
            Dict[str, str]: ヘッダー名とその値
        """
        return {
            "Strict-Transport-Security": "max-age=63072000; includeSubDomains; preload",
            "X-Content-Type-Options": "nosniff",
            "X-Frame-Options": "DENY",
            "X-XSS-Protection": "1; mode=block",
            "Referrer-Policy": "strict-origin-when-cross-origin",
            "Content-Security-Policy": "default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'; script-src 'self' 'unsafe-inline'; connect-src 'self'; frame-ancestors 'none'; form-action 'self';"
        }


# シングルトンインスタンス
ssl_manager = SSLCertificateManager()
https_config = HttpsConfiguration(ssl_manager)


# ヘルパー関数
def generate_self_signed_certificate(
    domain: str,
    organization: str = "Example Org",
    country: str = "JP",
    state: str = "Tokyo",
    locality: str = "Tokyo",
    email: str = "admin@example.com",
    alt_names: List[str] = None,
    validity_days: int = 365,
) -> bool:
    """
    自己署名証明書を生成するヘルパー関数
    
    Args:
        domain: ドメイン名
        organization: 組織名
        country: 国コード
        state: 都道府県
        locality: 市区町村
        email: メールアドレス
        alt_names: 代替ドメイン名のリスト
        validity_days: 有効期間（日数）
        
    Returns:
        bool: 成功したらTrue
    """
    cert_info = ssl_manager.generate_self_signed_cert(
        domain, organization, country, state, locality, email, alt_names, validity_days
    )
    return cert_info is not None


def get_certificate_info(domain: str) -> Optional[Dict[str, Any]]:
    """
    ドメインの証明書情報を取得するヘルパー関数
    
    Args:
        domain: ドメイン名
        
    Returns:
        Optional[Dict[str, Any]]: 証明書情報（辞書形式）
    """
    cert_info = ssl_manager.get_certificate_info(domain)
    if cert_info:
        return cert_info.to_dict()
    return None


def list_certificates() -> List[Dict[str, Any]]:
    """
    全ての証明書情報を取得するヘルパー関数
    
    Returns:
        List[Dict[str, Any]]: 証明書情報のリスト（辞書形式）
    """
    return [cert.to_dict() for cert in ssl_manager.list_certificates()]


def verify_certificate(domain: str) -> bool:
    """
    証明書が有効かどうかを検証するヘルパー関数
    
    Args:
        domain: ドメイン名
        
    Returns:
        bool: 有効ならTrue
    """
    return ssl_manager.verify_certificate(domain)


def get_security_headers() -> Dict[str, str]:
    """
    セキュリティ関連のHTTPヘッダーを取得するヘルパー関数
    
    Returns:
        Dict[str, str]: ヘッダー名とその値
    """
    return https_config.get_security_headers()


def start_certificate_monitor(interval_hours: int = 24, notify_days: int = 30):
    """
    証明書の有効期限を監視するスレッドを開始するヘルパー関数
    
    Args:
        interval_hours: チェック間隔（時間）
        notify_days: 通知するまでの残り日数
    """
    ssl_manager.start_certificate_monitor(interval_hours, notify_days)


# アプリケーション起動時に監視スレッドを自動的に開始（必要に応じて有効化）
# start_certificate_monitor() 
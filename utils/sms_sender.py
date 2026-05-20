"""
وحدة إرسال الرسائل النصية (SMS)
تدعم عدة مزودي خدمة: Twilio, Unifonic, وضع المحاكاة المحلية
يتم اختيار المزود عبر متغير البيئة SMS_PROVIDER
"""

import os
import logging

logger = logging.getLogger(__name__)

# ====================================================
# نص رسالة الإجازة المرضية
# ====================================================
SMS_TEMPLATE = "خطاك السوء {name} تم إصدار إجازة مرضية ليوم {days} برقم {code} ويمكنك الاطلاع عليها عبر تطبيق صحتي دمتم بصحة."

def build_sms_message(patient_name: str, leave_code: str, days: str = "واحد") -> str:
    """
    بناء نص رسالة الإجازة المرضية.

    المعاملات:
        patient_name: اسم المريض
        leave_code: رقم الإجازة المرضية (مثال: PSL24070700028)
        days: عدد أيام الإجازة (افتراضي: واحد)

    الإرجاع:
        نص الرسالة المنسق
    """
    return SMS_TEMPLATE.format(
        name=patient_name,
        code=leave_code,
        days=days
    )


# ====================================================
# مزود Twilio
# ====================================================
def send_via_twilio(to_phone: str, message: str) -> dict:
    """
    إرسال رسالة SMS عبر خدمة Twilio.

    متغيرات البيئة المطلوبة:
        TWILIO_ACCOUNT_SID: معرف حساب Twilio
        TWILIO_AUTH_TOKEN: رمز المصادقة
        TWILIO_FROM_NUMBER: رقم المرسل (مثال: +15551234567)
        SMS_SENDER_ID: معرف المرسل (اختياري، يُستخدم بدلاً من الرقم)
    """
    try:
        from twilio.rest import Client

        account_sid = os.environ.get('TWILIO_ACCOUNT_SID')
        auth_token = os.environ.get('TWILIO_AUTH_TOKEN')
        from_number = os.environ.get('TWILIO_FROM_NUMBER', os.environ.get('SMS_SENDER_ID', 'Sehhaty'))

        if not account_sid or not auth_token:
            return {
                'success': False,
                'error': 'بيانات Twilio غير مكتملة. يرجى تعيين TWILIO_ACCOUNT_SID و TWILIO_AUTH_TOKEN'
            }

        client = Client(account_sid, auth_token)
        msg = client.messages.create(
            body=message,
            from_=from_number,
            to=to_phone
        )

        logger.info(f"[Twilio] تم إرسال الرسالة بنجاح. SID: {msg.sid}")
        return {
            'success': True,
            'message_id': msg.sid,
            'provider': 'twilio'
        }

    except ImportError:
        return {
            'success': False,
            'error': 'مكتبة Twilio غير مثبتة. قم بتثبيتها: pip install twilio'
        }
    except Exception as e:
        logger.error(f"[Twilio] خطأ في إرسال الرسالة: {str(e)}")
        return {
            'success': False,
            'error': str(e)
        }


# ====================================================
# مزود Unifonic (خدمة سعودية محلية)
# ====================================================
def send_via_unifonic(to_phone: str, message: str) -> dict:
    """
    إرسال رسالة SMS عبر خدمة Unifonic.

    متغيرات البيئة المطلوبة:
        UNIFONIC_APP_SID: معرف تطبيق Unifonic
        SMS_SENDER_ID: معرف المرسل (مثال: Sehhaty)
    """
    try:
        import requests

        app_sid = os.environ.get('UNIFONIC_APP_SID')
        sender_id = os.environ.get('SMS_SENDER_ID', 'Sehhaty')

        if not app_sid:
            return {
                'success': False,
                'error': 'بيانات Unifonic غير مكتملة. يرجى تعيين UNIFONIC_APP_SID'
            }

        url = 'https://api.unifonic.com/rest/Messages/Send'
        payload = {
            'AppSid': app_sid,
            'SenderID': sender_id,
            'Body': message,
            'Recipient': to_phone,
            'responseType': 'JSON',
            'CorrelationID': '',
            'baseEncode': 'false'
        }

        response = requests.post(url, data=payload, timeout=15)
        result = response.json()

        if result.get('Success'):
            logger.info(f"[Unifonic] تم إرسال الرسالة بنجاح. MessageID: {result.get('data', {}).get('MessageID')}")
            return {
                'success': True,
                'message_id': result.get('data', {}).get('MessageID'),
                'provider': 'unifonic'
            }
        else:
            error_msg = result.get('Message', 'خطأ غير معروف')
            logger.error(f"[Unifonic] فشل إرسال الرسالة: {error_msg}")
            return {
                'success': False,
                'error': error_msg
            }

    except Exception as e:
        logger.error(f"[Unifonic] خطأ في إرسال الرسالة: {str(e)}")
        return {
            'success': False,
            'error': str(e)
        }


# ====================================================
# مزود Msegat (خدمة سعودية)
# ====================================================
def send_via_msegat(to_phone: str, message: str) -> dict:
    """
    إرسال رسالة SMS عبر خدمة Msegat.

    متغيرات البيئة المطلوبة:
        MSEGAT_USERNAME: اسم المستخدم
        MSEGAT_API_KEY: مفتاح API
        SMS_SENDER_ID: معرف المرسل (مثال: Sehhaty)
    """
    try:
        import requests
        import json

        username = os.environ.get('MSEGAT_USERNAME')
        api_key = os.environ.get('MSEGAT_API_KEY')
        sender_id = os.environ.get('SMS_SENDER_ID', 'Sehhaty')

        if not username or not api_key:
            return {
                'success': False,
                'error': 'بيانات Msegat غير مكتملة. يرجى تعيين MSEGAT_USERNAME و MSEGAT_API_KEY'
            }

        url = 'https://www.msegat.com/gw/sendsms.php'
        payload = {
            "userName": username,
            "numbers": to_phone,
            "userSender": sender_id,
            "apiKey": api_key,
            "msg": message,
            "msgEncoding": "UTF8"
        }

        headers = {'Content-Type': 'application/json'}
        response = requests.post(url, data=json.dumps(payload), headers=headers, timeout=15)
        result = response.json()

        if result.get('code') == '1':
            logger.info(f"[Msegat] تم إرسال الرسالة بنجاح.")
            return {
                'success': True,
                'message_id': result.get('id', ''),
                'provider': 'msegat'
            }
        else:
            error_msg = result.get('message', 'خطأ غير معروف')
            logger.error(f"[Msegat] فشل إرسال الرسالة: {error_msg}")
            return {
                'success': False,
                'error': error_msg
            }

    except Exception as e:
        logger.error(f"[Msegat] خطأ في إرسال الرسالة: {str(e)}")
        return {
            'success': False,
            'error': str(e)
        }


# ====================================================
# وضع المحاكاة المحلية (للاختبار)
# ====================================================
def send_via_simulation(to_phone: str, message: str) -> dict:
    """
    محاكاة إرسال SMS محلياً للاختبار (لا يرسل رسالة حقيقية).
    يسجل الرسالة في ملف السجل فقط.
    """
    logger.info(f"[SMS-SIMULATION] إلى: {to_phone}")
    logger.info(f"[SMS-SIMULATION] النص: {message}")
    print(f"\n{'='*60}")
    print(f"[محاكاة SMS] المرسل: Sehhaty")
    print(f"[محاكاة SMS] إلى: {to_phone}")
    print(f"[محاكاة SMS] النص:\n{message}")
    print(f"{'='*60}\n")
    return {
        'success': True,
        'message_id': 'SIM-' + str(hash(to_phone + message))[-8:],
        'provider': 'simulation',
        'note': 'هذه محاكاة - لم يتم إرسال رسالة حقيقية'
    }


# ====================================================
# الدالة الرئيسية لإرسال SMS
# ====================================================
def send_sms(to_phone: str, patient_name: str, leave_code: str, days: str = "واحد") -> dict:
    """
    إرسال رسالة SMS للمريض عند إصدار الإجازة المرضية.

    يختار المزود تلقائياً بناءً على متغير البيئة SMS_PROVIDER:
        - 'twilio'     → Twilio (افتراضي إذا كانت بيانات Twilio متوفرة)
        - 'unifonic'   → Unifonic (خدمة سعودية)
        - 'msegat'     → Msegat (خدمة سعودية)
        - 'simulation' → محاكاة محلية للاختبار (الافتراضي)

    المعاملات:
        to_phone: رقم هاتف المريض (مثال: 966501234567 أو +966501234567)
        patient_name: اسم المريض
        leave_code: رقم الإجازة المرضية
        days: عدد أيام الإجازة

    الإرجاع:
        قاموس يحتوي على: success (bool), message_id, provider, error (عند الفشل)
    """
    if not to_phone:
        logger.warning("[SMS] رقم الهاتف فارغ - تم تخطي إرسال الرسالة")
        return {
            'success': False,
            'error': 'رقم الهاتف فارغ',
            'skipped': True
        }

    # تنظيف رقم الهاتف
    phone = to_phone.strip().replace(' ', '').replace('-', '')
    if not phone.startswith('+'):
        # إضافة رمز الدولة السعودية إذا لم يكن موجوداً
        if phone.startswith('05') or phone.startswith('5'):
            phone = '+966' + phone.lstrip('0')
        elif phone.startswith('966'):
            phone = '+' + phone
        else:
            phone = '+' + phone

    # بناء نص الرسالة
    message = build_sms_message(patient_name, leave_code, days)

    # اختيار المزود
    provider = os.environ.get('SMS_PROVIDER', 'simulation').lower()

    logger.info(f"[SMS] إرسال رسالة عبر {provider} إلى {phone}")

    if provider == 'twilio':
        result = send_via_twilio(phone, message)
    elif provider == 'unifonic':
        result = send_via_unifonic(phone, message)
    elif provider == 'msegat':
        result = send_via_msegat(phone, message)
    else:
        # الوضع الافتراضي: محاكاة
        result = send_via_simulation(phone, message)
        result['simulated'] = True

    # إضافة نص الرسالة دائماً للعرض في الواجهة
    result['message_body'] = message
    return result

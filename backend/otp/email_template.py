from datetime import datetime, timezone

from .config import OTP_EXPIRY_MINUTES


def _purpose_heading(purpose: str) -> str:
    if purpose == "registration":
        return "Verify Your Account"
    if purpose == "login":
        return "Verify Your Sign In"
    return "Verify Your Account"


def build_otp_html(otp: str, purpose: str) -> str:
    heading = _purpose_heading(purpose)
    year = datetime.now(tz=timezone.utc).year
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Verify Your Account</title>
</head>

<body style="
  margin:0;
  padding:0;
  background:#f4f7fb;
  font-family:Arial, sans-serif;
">

  <table width="100%" cellpadding="0" cellspacing="0">
    <tr>
      <td align="center" style="padding:40px 15px;">

        <table width="600" cellpadding="0" cellspacing="0" style="
          background:#ffffff;
          border-radius:16px;
          overflow:hidden;
          box-shadow:0 4px 20px rgba(0,0,0,0.08);
        ">

          <tr>
            <td style="
              background:#111827;
              padding:30px;
              text-align:center;
            ">
              <h1 style="
                color:white;
                margin:0;
                font-size:28px;
              ">
                MacNik
              </h1>

              <p style="
                color:#9ca3af;
                margin-top:8px;
                font-size:14px;
              ">
                Secure Verification System
              </p>
            </td>
          </tr>

          <tr>
            <td style="padding:40px 30px;">

              <h2 style="
                margin:0 0 15px;
                color:#111827;
                font-size:24px;
              ">
                {heading}
              </h2>

              <p style="
                color:#4b5563;
                font-size:16px;
                line-height:1.6;
              ">
                Use the verification code below to continue signing in.
              </p>

              <div style="
                margin:35px 0;
                text-align:center;
              ">

                <span style="
                  display:inline-block;
                  background:#f3f4f6;
                  border:2px dashed #2563eb;
                  color:#111827;
                  font-size:36px;
                  letter-spacing:10px;
                  font-weight:bold;
                  padding:18px 30px;
                  border-radius:14px;
                ">
                  {otp}
                </span>

              </div>

              <p style="
                color:#6b7280;
                font-size:14px;
                line-height:1.6;
              ">
                This OTP will expire in
                <strong>{OTP_EXPIRY_MINUTES} minutes</strong>.
              </p>

              <p style="
                color:#6b7280;
                font-size:14px;
                line-height:1.6;
              ">
                If you didn't request this verification,
                you can safely ignore this email.
              </p>

            </td>
          </tr>

          <tr>
            <td style="
              background:#f9fafb;
              padding:25px;
              text-align:center;
              border-top:1px solid #e5e7eb;
            ">

              <p style="
                margin:0;
                color:#9ca3af;
                font-size:12px;
              ">
                © {year} MacNik. All rights reserved.
              </p>

            </td>
          </tr>

        </table>

      </td>
    </tr>
  </table>

</body>
</html>"""


def build_otp_plain_text(otp: str, purpose: str) -> str:
    heading = _purpose_heading(purpose)
    return (
        f"MacNik — {heading}\n\n"
        f"Your verification code is: {otp}\n\n"
        f"This OTP will expire in {OTP_EXPIRY_MINUTES} minutes.\n\n"
        "If you didn't request this verification, you can safely ignore this email.\n"
    )

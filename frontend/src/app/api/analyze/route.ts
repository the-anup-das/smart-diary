import { NextRequest, NextResponse } from 'next/server';

const BACKEND_URL = process.env.INTERNAL_BACKEND_URL || process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8000';

export async function POST(request: NextRequest) {
  try {
    const sessionCookie = request.cookies.get('session')?.value;
    const headers: Record<string, string> = { 'Content-Type': 'application/json' };
    if (sessionCookie) {
      headers['Cookie'] = `session=${sessionCookie}`;
    }

    const res = await fetch(`${BACKEND_URL}/api/analyze`, {
      method: 'POST',
      headers,
      cache: 'no-store',
    });

    const data = await res.text();
    return new NextResponse(data, {
      status: res.status,
      headers: { 'Content-Type': res.headers.get('content-type') || 'application/json' },
    });
  } catch (error: any) {
    return NextResponse.json(
      { detail: `Proxy to backend failed: ${error.message}` },
      { status: 502 }
    );
  }
}

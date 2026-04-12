import { NextRequest, NextResponse } from 'next/server';

const BACKEND_URL = process.env.INTERNAL_BACKEND_URL || process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8000';

export async function GET(request: NextRequest) {
  try {
    const sessionCookie = request.cookies.get('session')?.value;
    const headers: Record<string, string> = {};
    if (sessionCookie) headers['Cookie'] = `session=${sessionCookie}`;

    const res = await fetch(`${BACKEND_URL}/api/entries/history`, {
      method: 'GET',
      headers,
      cache: 'no-store',
    });

    const data = await res.text();
    return new NextResponse(data, {
      status: res.status,
      headers: { 'Content-Type': res.headers.get('content-type') || 'application/json' },
    });
  } catch (error: any) {
    return NextResponse.json({ detail: `Proxy error: ${error.message}` }, { status: 502 });
  }
}

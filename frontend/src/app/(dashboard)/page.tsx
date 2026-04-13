import { JournalEditor } from "@/components/diary/JournalEditor"
import { cookies } from "next/headers"
import { redirect } from "next/navigation"

export default async function HomePage() {
  const cookieStore = await cookies();
  const sessionCookie = cookieStore.get('session');
  
  if (!sessionCookie || !sessionCookie.value) {
    redirect('/login');
  }

  let initialContent = "";
  let initialId: string | null = null;
  let needsLogin = false;
  let backendOffline = false;

  try {
    // Next.js explicitly caches NEXT_PUBLIC vars locally. We must use an explicit INTERNAL variable to safely traverse Docker's DNS loops.
    const BACKEND_URL = process.env.INTERNAL_BACKEND_URL || process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8000';
    const res = await fetch(`${BACKEND_URL}/api/entries/today`, {
      method: "GET",
      headers: { Cookie: `session=${sessionCookie.value}` },
      cache: 'no-store'
    });
    
    if (res.ok) {
        const data = await res.json();
        initialContent = data.content || "";
        initialId = data.id || null;
    } else if (res.status === 401) {
        needsLogin = true;
    }
  } catch (error: any) {
    backendOffline = true;
  }

  if (needsLogin) {
    redirect('/login');
  }

  if (backendOffline) {
    return (
      <div className="h-full w-full max-w-4xl mx-auto flex flex-col items-center justify-center fade-in px-4">
        <div className="p-8 text-center bg-red-50 dark:bg-red-500/10 border border-red-200 dark:border-red-500/20 rounded-2xl max-w-lg shadow-xl backdrop-blur-md">
          <h2 className="text-xl font-bold text-red-600 dark:text-red-400 mb-3">Backend Engine Offline</h2>
          <p className="text-gray-700 dark:text-gray-300 leading-relaxed text-sm">
            The Next.js React UI is perfectly mapped, but it cannot securely reach the Python FastAPI server.
            <br/><br/>
            Please verify that your <code className="bg-black/10 dark:bg-white/10 px-2 py-0.5 rounded text-red-600 dark:text-red-400">diary-backend</code> Docker container is running and healthy on Port 8000.
          </p>
        </div>
      </div>
    )
  }

  return (
    <div className="h-full w-full max-w-5xl mx-auto flex justify-center fade-in">
      {/* We pass the SSR fetched draft right back into Tiptap's payload */}
      <JournalEditor initialContent={initialContent} initialId={initialId} />
    </div>
  )
}

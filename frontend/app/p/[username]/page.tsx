import { PublicProfileView } from "@/components/profile/PublicProfileView";

export default async function PublicProfilePage({ params }: { params: Promise<{ username: string }> }) {
  const { username } = await params;
  return <PublicProfileView username={username} />;
}

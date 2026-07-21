"use client";

import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Users, ScrollText } from "lucide-react";
import { UsersPage } from "./users";
import { AuditLogsPage } from "./audit-logs";

export function UserSettingsPage() {
  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-foreground">User Settings</h2>
        <p className="text-muted-foreground">Manage web application accounts and review system activity</p>
      </div>

      <Tabs defaultValue="users">
        <TabsList>
          <TabsTrigger value="users" className="gap-1.5">
            <Users className="w-4 h-4" /> Users
          </TabsTrigger>
          <TabsTrigger value="audit-logs" className="gap-1.5">
            <ScrollText className="w-4 h-4" /> Audit Logs
          </TabsTrigger>
        </TabsList>
        <TabsContent value="users">
          <UsersPage />
        </TabsContent>
        <TabsContent value="audit-logs">
          <AuditLogsPage />
        </TabsContent>
      </Tabs>
    </div>
  );
}

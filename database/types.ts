export type Json =
  | string
  | number
  | boolean
  | null
  | { [key: string]: Json | undefined }
  | Json[];

export type Database = {
  // Allows to automatically instantiate createClient with right options
  // instead of createClient<Database, { PostgrestVersion: 'XX' }>(URL, KEY)
  __InternalSupabase: {
    PostgrestVersion: "14.5";
  };
  public: {
    Tables: {
      conversations: {
        Row: {
          created_at: string;
          id: string;
        };
        Insert: {
          created_at?: string;
          id?: string;
        };
        Update: {
          created_at?: string;
          id?: string;
        };
        Relationships: [];
      };
      food_logs: {
        Row: {
          created_at: string;
          food_id: string;
          id: string;
          quantity_g: number;
        };
        Insert: {
          created_at?: string;
          food_id: string;
          id?: string;
          quantity_g: number;
        };
        Update: {
          created_at?: string;
          food_id?: string;
          id?: string;
          quantity_g?: number;
        };
        Relationships: [
          {
            foreignKeyName: "food_logs_food_id_fkey";
            columns: ["food_id"];
            isOneToOne: false;
            referencedRelation: "foods";
            referencedColumns: ["id"];
          },
        ];
      };
      foods: {
        Row: {
          calories_kcal: number;
          carbs_g: number;
          created_at: string;
          embedding: string | null;
          fat_g: number;
          id: string;
          name: string;
          protein_g: number;
        };
        Insert: {
          calories_kcal: number;
          carbs_g: number;
          created_at?: string;
          embedding?: string | null;
          fat_g: number;
          id?: string;
          name: string;
          protein_g: number;
        };
        Update: {
          calories_kcal?: number;
          carbs_g?: number;
          created_at?: string;
          embedding?: string | null;
          fat_g?: number;
          id?: string;
          name?: string;
          protein_g?: number;
        };
        Relationships: [];
      };
      goals: {
        Row: {
          calories_kcal: number;
          carbs_g: number;
          created_at: string;
          fat_g: number;
          goal: string;
          id: string;
          protein_g: number;
          weight_kg: number;
        };
        Insert: {
          calories_kcal: number;
          carbs_g: number;
          created_at?: string;
          fat_g: number;
          goal: string;
          id?: string;
          protein_g: number;
          weight_kg: number;
        };
        Update: {
          calories_kcal?: number;
          carbs_g?: number;
          created_at?: string;
          fat_g?: number;
          goal?: string;
          id?: string;
          protein_g?: number;
          weight_kg?: number;
        };
        Relationships: [];
      };
      llm_invocations: {
        Row: {
          conversation_id: string | null;
          created_at: string;
          id: string;
          raw_usage_metadata: Json;
          total_cost: number;
        };
        Insert: {
          conversation_id?: string | null;
          created_at?: string;
          id?: string;
          raw_usage_metadata: Json;
          total_cost: number;
        };
        Update: {
          conversation_id?: string | null;
          created_at?: string;
          id?: string;
          raw_usage_metadata?: Json;
          total_cost?: number;
        };
        Relationships: [
          {
            foreignKeyName: "llm_invocations_conversation_id_fkey";
            columns: ["conversation_id"];
            isOneToOne: false;
            referencedRelation: "conversations";
            referencedColumns: ["id"];
          },
        ];
      };
      measurements: {
        Row: {
          created_at: string;
          id: string;
          weight_kg: number;
        };
        Insert: {
          created_at?: string;
          id?: string;
          weight_kg: number;
        };
        Update: {
          created_at?: string;
          id?: string;
          weight_kg?: number;
        };
        Relationships: [];
      };
      messages: {
        Row: {
          conversation_id: string;
          created_at: string;
          id: string;
          raw_content: Json;
        };
        Insert: {
          conversation_id: string;
          created_at?: string;
          id?: string;
          raw_content: Json;
        };
        Update: {
          conversation_id?: string;
          created_at?: string;
          id?: string;
          raw_content?: Json;
        };
        Relationships: [
          {
            foreignKeyName: "messages_conversation_id_fkey";
            columns: ["conversation_id"];
            isOneToOne: false;
            referencedRelation: "conversations";
            referencedColumns: ["id"];
          },
        ];
      };
    };
    Views: {
      v_daily_food_logs_with_foods: {
        Row: {
          day: string | null;
          food_calories_kcal: number | null;
          food_carbs_g: number | null;
          food_fat_g: number | null;
          food_name: string | null;
          food_protein_g: number | null;
          log_created_at: string | null;
          log_food_id: string | null;
          log_id: string | null;
          log_quantity_g: number | null;
        };
        Relationships: [
          {
            foreignKeyName: "food_logs_food_id_fkey";
            columns: ["log_food_id"];
            isOneToOne: false;
            referencedRelation: "foods";
            referencedColumns: ["id"];
          },
        ];
      };
      v_daily_macros: {
        Row: {
          day: string | null;
          total_calories_kcal: number | null;
          total_carbs_g: number | null;
          total_fat_g: number | null;
          total_protein_g: number | null;
        };
        Relationships: [];
      };
      v_total_llm_cost: {
        Row: {
          total_cost: number | null;
        };
        Relationships: [];
      };
    };
    Functions: {
      [_ in never]: never;
    };
    Enums: {
      [_ in never]: never;
    };
    CompositeTypes: {
      [_ in never]: never;
    };
  };
};

type DatabaseWithoutInternals = Omit<Database, "__InternalSupabase">;

type DefaultSchema = DatabaseWithoutInternals[Extract<
  keyof Database,
  "public"
>];

export type Tables<
  DefaultSchemaTableNameOrOptions extends
    | keyof (DefaultSchema["Tables"] & DefaultSchema["Views"])
    | { schema: keyof DatabaseWithoutInternals },
  TableName extends DefaultSchemaTableNameOrOptions extends {
    schema: keyof DatabaseWithoutInternals;
  }
    ? keyof (DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Tables"] &
        DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Views"])
    : never = never,
> = DefaultSchemaTableNameOrOptions extends {
  schema: keyof DatabaseWithoutInternals;
}
  ? (DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Tables"] &
      DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Views"])[TableName] extends {
      Row: infer R;
    }
    ? R
    : never
  : DefaultSchemaTableNameOrOptions extends keyof (DefaultSchema["Tables"] &
        DefaultSchema["Views"])
    ? (DefaultSchema["Tables"] &
        DefaultSchema["Views"])[DefaultSchemaTableNameOrOptions] extends {
        Row: infer R;
      }
      ? R
      : never
    : never;

export type TablesInsert<
  DefaultSchemaTableNameOrOptions extends
    | keyof DefaultSchema["Tables"]
    | { schema: keyof DatabaseWithoutInternals },
  TableName extends DefaultSchemaTableNameOrOptions extends {
    schema: keyof DatabaseWithoutInternals;
  }
    ? keyof DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Tables"]
    : never = never,
> = DefaultSchemaTableNameOrOptions extends {
  schema: keyof DatabaseWithoutInternals;
}
  ? DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Tables"][TableName] extends {
      Insert: infer I;
    }
    ? I
    : never
  : DefaultSchemaTableNameOrOptions extends keyof DefaultSchema["Tables"]
    ? DefaultSchema["Tables"][DefaultSchemaTableNameOrOptions] extends {
        Insert: infer I;
      }
      ? I
      : never
    : never;

export type TablesUpdate<
  DefaultSchemaTableNameOrOptions extends
    | keyof DefaultSchema["Tables"]
    | { schema: keyof DatabaseWithoutInternals },
  TableName extends DefaultSchemaTableNameOrOptions extends {
    schema: keyof DatabaseWithoutInternals;
  }
    ? keyof DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Tables"]
    : never = never,
> = DefaultSchemaTableNameOrOptions extends {
  schema: keyof DatabaseWithoutInternals;
}
  ? DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Tables"][TableName] extends {
      Update: infer U;
    }
    ? U
    : never
  : DefaultSchemaTableNameOrOptions extends keyof DefaultSchema["Tables"]
    ? DefaultSchema["Tables"][DefaultSchemaTableNameOrOptions] extends {
        Update: infer U;
      }
      ? U
      : never
    : never;

export type Enums<
  DefaultSchemaEnumNameOrOptions extends
    | keyof DefaultSchema["Enums"]
    | { schema: keyof DatabaseWithoutInternals },
  EnumName extends DefaultSchemaEnumNameOrOptions extends {
    schema: keyof DatabaseWithoutInternals;
  }
    ? keyof DatabaseWithoutInternals[DefaultSchemaEnumNameOrOptions["schema"]]["Enums"]
    : never = never,
> = DefaultSchemaEnumNameOrOptions extends {
  schema: keyof DatabaseWithoutInternals;
}
  ? DatabaseWithoutInternals[DefaultSchemaEnumNameOrOptions["schema"]]["Enums"][EnumName]
  : DefaultSchemaEnumNameOrOptions extends keyof DefaultSchema["Enums"]
    ? DefaultSchema["Enums"][DefaultSchemaEnumNameOrOptions]
    : never;

export type CompositeTypes<
  PublicCompositeTypeNameOrOptions extends
    | keyof DefaultSchema["CompositeTypes"]
    | { schema: keyof DatabaseWithoutInternals },
  CompositeTypeName extends PublicCompositeTypeNameOrOptions extends {
    schema: keyof DatabaseWithoutInternals;
  }
    ? keyof DatabaseWithoutInternals[PublicCompositeTypeNameOrOptions["schema"]]["CompositeTypes"]
    : never = never,
> = PublicCompositeTypeNameOrOptions extends {
  schema: keyof DatabaseWithoutInternals;
}
  ? DatabaseWithoutInternals[PublicCompositeTypeNameOrOptions["schema"]]["CompositeTypes"][CompositeTypeName]
  : PublicCompositeTypeNameOrOptions extends keyof DefaultSchema["CompositeTypes"]
    ? DefaultSchema["CompositeTypes"][PublicCompositeTypeNameOrOptions]
    : never;

export const Constants = {
  public: {
    Enums: {},
  },
} as const;
